"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  listConversations,
  renameConversation,
  deleteConversation,
} from "@/lib/api/bus-agent";
import type { ConversationListItem } from "@/types/bus-booking";

export interface UseConversationsReturn {
  conversations: ConversationListItem[];
  isLoading: boolean;
  searchQuery: string;
  hasMore: boolean;
  setSearchQuery: (query: string) => void;
  refresh: () => Promise<void>;
  loadMore: () => Promise<void>;
  rename: (id: string, newTitle: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
}

export function useConversations(): UseConversationsReturn {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [nextCursorId, setNextCursorId] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  // Ref to debounce search requests
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const fetchConversations = useCallback(
    async (
      cursor?: string | null,
      cursorId?: string | null,
      search?: string | null,
      isInitial: boolean = false,
    ) => {
      setIsLoading(true);
      try {
        const res = await listConversations({
          cursor,
          cursorId,
          search,
          limit: 20,
        });

        if (res.success) {
          setConversations((prev) => {
            if (isInitial) {
              return res.conversations;
            }
            // Deduplicate by ID when appending pages
            const existingIds = new Set(prev.map((c) => c.id));
            const freshItems = res.conversations.filter(
              (c) => !existingIds.has(c.id),
            );
            return [...prev, ...freshItems];
          });

          setNextCursor(res.next_cursor);
          setNextCursorId(res.next_cursor_id);
          setHasMore(res.has_more);
        }
      } catch (err) {
        console.error("Failed to load conversations:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  // Initial load
  useEffect(() => {
    let ignore = false;
    async function loadInitial() {
      setIsLoading(true);
      try {
        const res = await listConversations({ limit: 20 });
        if (!ignore && res.success) {
          setConversations(res.conversations);
          setNextCursor(res.next_cursor);
          setNextCursorId(res.next_cursor_id);
          setHasMore(res.has_more);
        }
      } catch (err) {
        console.error("Failed to load conversations:", err);
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }
    loadInitial();
    return () => {
      ignore = true;
    };
  }, []);

  // Handle Search with 300ms debounce
  const handleSetSearchQuery = (query: string) => {
    setSearchQuery(query);
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      fetchConversations(null, null, query, true);
    }, 300);
  };

  const refresh = useCallback(async () => {
    await fetchConversations(null, null, searchQuery, true);
  }, [fetchConversations, searchQuery]);

  const loadMore = useCallback(async () => {
    if (isLoading || !hasMore || !nextCursor || !nextCursorId) return;
    await fetchConversations(nextCursor, nextCursorId, searchQuery, false);
  }, [isLoading, hasMore, nextCursor, nextCursorId, searchQuery, fetchConversations]);

  const rename = useCallback(
    async (id: string, newTitle: string) => {
      const trimmed = newTitle.trim();
      if (!trimmed) return;

      // Optimistic update
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c)),
      );

      try {
        await renameConversation(id, trimmed);
      } catch (err) {
        console.error("Failed to rename conversation:", err);
        // Refresh to revert on error
        await refresh();
      }
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      // Optimistic delete
      setConversations((prev) => prev.filter((c) => c.id !== id));

      try {
        await deleteConversation(id);
      } catch (err) {
        console.error("Failed to delete conversation:", err);
        await refresh();
      }
    },
    [refresh],
  );

  return {
    conversations,
    isLoading,
    searchQuery,
    hasMore,
    setSearchQuery: handleSetSearchQuery,
    refresh,
    loadMore,
    rename,
    remove,
  };
}
