"use client";

import React, { createContext, useContext } from "react";
import {
  useConversations,
  type UseConversationsReturn,
} from "@/hooks/use-conversations";

const ConversationsContext = createContext<UseConversationsReturn | null>(null);

export function ConversationsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const conversationsState = useConversations();

  return (
    <ConversationsContext.Provider value={conversationsState}>
      {children}
    </ConversationsContext.Provider>
  );
}

export function useConversationsContext(): UseConversationsReturn {
  const context = useContext(ConversationsContext);
  if (!context) {
    throw new Error(
      "useConversationsContext must be used within a ConversationsProvider",
    );
  }
  return context;
}
