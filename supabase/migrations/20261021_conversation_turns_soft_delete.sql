-- =============================================================================
-- Migration: 20261021_conversation_turns_soft_delete.sql
-- Description:
--   1. Add deleted_at (soft-delete) column to conversations
--   2. Create conversation_turns table — one row per user+assistant pair,
--      with support for pending turns and unmatched messages
--   3. Migrate existing data from chat_messages with reliable pairing,
--      preserving all messages (both matched and unmatched)
--   4. Add RLS WITH CHECK on both tables (read + write ownership)
--   5. Update conversations RLS to enforce deleted_at IS NULL
--
-- SAFE MIGRATION:
--   - chat_messages is PRESERVED (not dropped).
--   - Idempotent: ON CONFLICT DO NOTHING prevents duplicate inserts on re-run.
--
-- CONCURRENCY NOTE:
--   - conversation_turns has a UNIQUE (conversation_id, turn_number) constraint.
--   - The application uses FOR UPDATE on the parent conversations row to serialise
--     turn_number allocation; see _create_pending_turn() in main.py.
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. ADD deleted_at TO conversations
-- =============================================================================

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Partial index: only non-deleted rows, ordered newest-first for sidebar queries
CREATE INDEX IF NOT EXISTS idx_conversations_user_active
    ON conversations (auth_user_id, updated_at DESC, id DESC)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 2. CREATE conversation_turns
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversation_turns (
    id                UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_number       INTEGER NOT NULL,
    user_message      TEXT,           -- NULL if turn started by standalone assistant message
    assistant_message TEXT,           -- NULL while pending or when agent failed
    metadata          JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT conversation_turns_unique_turn
        UNIQUE (conversation_id, turn_number),
    CONSTRAINT conversation_turns_not_empty
        CHECK (user_message IS NOT NULL OR assistant_message IS NOT NULL)
);

-- Fast retrieval in turn order
CREATE INDEX IF NOT EXISTS idx_conversation_turns_conv_turn
    ON conversation_turns (conversation_id, turn_number ASC);

-- =============================================================================
-- 3. RLS ON conversation_turns (WITH CHECK enforces write ownership)
-- =============================================================================

ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'conversation_turns'
          AND policyname = 'conversation_turns_owner_all'
    ) THEN
        -- USING  → rows visible for SELECT / UPDATE-existing / DELETE
        -- WITH CHECK → rows allowed for INSERT / UPDATE-new-value
        -- Both reference only non-deleted conversations owned by the caller.
        -- This prevents new turns being written to a soft-deleted conversation.
        CREATE POLICY conversation_turns_owner_all ON conversation_turns
            FOR ALL
            USING (
                conversation_id IN (
                    SELECT id FROM conversations
                    WHERE auth_user_id = auth.uid()
                      AND deleted_at IS NULL
                )
            )
            WITH CHECK (
                conversation_id IN (
                    SELECT id FROM conversations
                    WHERE auth_user_id = auth.uid()
                      AND deleted_at IS NULL
                )
            );
    END IF;
END $$;

-- =============================================================================
-- 4. UPDATE conversations RLS
-- =============================================================================

DO $$
BEGIN
    DROP POLICY IF EXISTS conversations_owner_all ON conversations;

    CREATE POLICY conversations_owner_all ON conversations
        FOR ALL
        USING  (auth_user_id = auth.uid() AND deleted_at IS NULL)
        WITH CHECK (auth_user_id = auth.uid());
END $$;

-- =============================================================================
-- 5. MIGRATE DATA: chat_messages → conversation_turns
--
-- Pairing strategy:
--   Within each conversation, order all messages deterministically:
--     (created_at ASC, CASE WHEN role = 'user' THEN 0 ELSE 1 END ASC, id ASC)
--   We partition messages into turns such that each user message pairs with
--   its immediately following assistant message.
--   If an assistant message has no preceding user message (e.g. initial greeting),
--   it is preserved as a turn with user_message = NULL.
--   If a user message has no following assistant message, it is preserved
--   with assistant_message = NULL.
--   Zero messages are lost.
-- =============================================================================

DO $$
DECLARE
    migrated_count INTEGER := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        WITH ordered_msgs AS (
            SELECT
                id,
                conversation_id,
                role,
                content,
                metadata,
                created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY conversation_id
                    ORDER BY
                        created_at ASC,
                        CASE WHEN role = 'user' THEN 0 ELSE 1 END ASC,
                        id ASC
                ) AS seq
            FROM chat_messages
        ),
        user_turns AS (
            -- User messages matched with immediate next assistant message if seq + 1 is assistant
            SELECT
                u.conversation_id,
                u.content AS user_message,
                a.content AS assistant_message,
                COALESCE(a.metadata, u.metadata) AS metadata,
                u.created_at,
                u.seq AS sort_key
            FROM ordered_msgs u
            LEFT JOIN ordered_msgs a ON
                a.conversation_id = u.conversation_id
                AND a.seq = u.seq + 1
                AND a.role = 'assistant'
            WHERE u.role = 'user'
        ),
        orphan_assistant_turns AS (
            -- Assistant messages that were NOT preceded by a user message at seq - 1
            SELECT
                a.conversation_id,
                NULL::TEXT AS user_message,
                a.content AS assistant_message,
                a.metadata,
                a.created_at,
                a.seq AS sort_key
            FROM ordered_msgs a
            WHERE a.role = 'assistant'
              AND NOT EXISTS (
                  SELECT 1
                  FROM ordered_msgs u
                  WHERE u.conversation_id = a.conversation_id
                    AND u.seq = a.seq - 1
                    AND u.role = 'user'
              )
        ),
        all_turns AS (
            SELECT * FROM user_turns
            UNION ALL
            SELECT * FROM orphan_assistant_turns
        ),
        numbered_turns AS (
            SELECT
                conversation_id,
                ROW_NUMBER() OVER (
                    PARTITION BY conversation_id
                    ORDER BY sort_key ASC
                ) AS turn_number,
                user_message,
                assistant_message,
                metadata,
                created_at
            FROM all_turns
        )
        INSERT INTO conversation_turns
            (conversation_id, turn_number, user_message, assistant_message, metadata, created_at)
        SELECT
            conversation_id,
            turn_number,
            user_message,
            assistant_message,
            metadata,
            created_at
        FROM numbered_turns
        ON CONFLICT (conversation_id, turn_number) DO NOTHING;

        GET DIAGNOSTICS migrated_count = ROW_COUNT;
    END IF;

    RAISE NOTICE 'Migration complete: % turns inserted into conversation_turns.', migrated_count;
END $$;

COMMIT;

