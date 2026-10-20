-- =============================================================================
-- Migration: 20261020_chat_history.sql
-- Description: Create conversations and chat_messages tables for persistent
--              chat history and sidebar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for ordering conversations newest-first per user, with id tie-breaker for cursor pagination
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated 
    ON conversations (auth_user_id, updated_at DESC, id DESC);

-- Index for title search
CREATE INDEX IF NOT EXISTS idx_conversations_user_title 
    ON conversations (auth_user_id, title text_pattern_ops);

-- =============================================================================
-- 2. CHAT_MESSAGES
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast sequential message retrieval per conversation
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created 
    ON chat_messages (conversation_id, created_at ASC);

-- =============================================================================
-- 3. ROW LEVEL SECURITY (RLS)
-- =============================================================================
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'conversations' AND policyname = 'conversations_owner_all'
    ) THEN
        CREATE POLICY conversations_owner_all ON conversations
            FOR ALL USING (auth_user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'chat_messages' AND policyname = 'chat_messages_owner_all'
    ) THEN
        CREATE POLICY chat_messages_owner_all ON chat_messages
            FOR ALL USING (
                conversation_id IN (
                    SELECT id FROM conversations WHERE auth_user_id = auth.uid()
                )
            );
    END IF;
END $$;

