"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  MoreHorizontal,
  Trash2,
  Loader2,
} from "lucide-react";
import type { ConversationListItem } from "@/types/bus-booking";

export interface NavHistoryProps {
  conversations: ConversationListItem[];
  isLoading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  onRename?: (id: string, newTitle: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

interface GroupedConversations {
  today: ConversationListItem[];
  yesterday: ConversationListItem[];
  previous7Days: ConversationListItem[];
  older: ConversationListItem[];
}

export function NavHistory({
  conversations,
  isLoading,
  hasMore,
  onLoadMore,
  onDelete,
}: NavHistoryProps) {
  const params = useParams();
  const router = useRouter();
  const activeConversationId = params?.conversationId as string | undefined;

  // Group conversations by relative date using vanilla Date calculations
  const groups = useMemo<GroupedConversations>(() => {
    const now = new Date();
    const startOfToday = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    ).getTime();
    const startOfYesterday = startOfToday - 86400000;
    const sevenDaysAgo = startOfToday - 6 * 86400000;

    const result: GroupedConversations = {
      today: [],
      yesterday: [],
      previous7Days: [],
      older: [],
    };

    for (const item of conversations) {
      const itemTime = new Date(item.updated_at).getTime();
      if (itemTime >= startOfToday) {
        result.today.push(item);
      } else if (itemTime >= startOfYesterday) {
        result.yesterday.push(item);
      } else if (itemTime >= sevenDaysAgo) {
        result.previous7Days.push(item);
      } else {
        result.older.push(item);
      }
    }

    return result;
  }, [conversations]);

  const handleDelete = async (id: string) => {
    await onDelete(id);
    if (activeConversationId === id) {
      router.push("/chat");
    }
  };

  const renderSection = (title: string, items: ConversationListItem[]) => {
    if (items.length === 0) return null;

    return (
      <div key={title} className="space-y-1 py-1">
        <div className="px-2 text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
          {title}
        </div>
        <SidebarMenu>
          {items.map((item) => {
            const isActive = activeConversationId === item.id;

            return (
              <SidebarMenuItem key={item.id} className="group/item relative">
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <SidebarMenuButton
                        size="lg"
                        isActive={isActive}
                        className={
                          isActive
                            ? "h-10 bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                            : "h-10"
                        }
                        render={<Link href={`/chat/${item.id}`} />}
                      >
                        <span className="truncate text-sm">{item.title}</span>
                      </SidebarMenuButton>
                    }
                  />
                  <TooltipContent
                    side="right"
                    align="center"
                    sideOffset={8}
                    className="max-w-xs break-words text-xs shadow-md z-50 font-normal"
                  >
                    {item.title}
                  </TooltipContent>
                </Tooltip>

                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <SidebarMenuAction
                        showOnHover
                        className="text-muted-foreground hover:text-foreground"
                      />
                    }
                  >
                    <MoreHorizontal className="size-3.5" />
                    <span className="sr-only">Options</span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="right" align="start">
                    <DropdownMenuItem
                      onClick={() => handleDelete(item.id)}
                      className="text-xs gap-2 text-destructive focus:text-destructive cursor-pointer"
                    >
                      <Trash2 className="size-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </div>
    );
  };

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden px-2 space-y-2">
      <div className="flex items-center justify-between px-2 pt-1">
        <SidebarGroupLabel className="p-0 text-xs font-semibold text-muted-foreground">
          Recent Chats
        </SidebarGroupLabel>
      </div>

      <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-11rem)] pr-1">
        {conversations.length === 0 && !isLoading ? (
          <Empty className="gap-2 border border-dashed p-4 my-2">
            <EmptyHeader>
              <EmptyTitle className="text-xs font-medium">No history yet</EmptyTitle>
              <EmptyDescription className="text-[11px] text-muted-foreground">
                Your recent bus searches and bookings will appear here.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <>
            {renderSection("Today", groups.today)}
            {renderSection("Yesterday", groups.yesterday)}
            {renderSection("Previous 7 Days", groups.previous7Days)}
            {renderSection("Older", groups.older)}

            {/* Load More Button at bottom */}
            {hasMore && (
              <div className="pt-2 pb-1 text-center">
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={onLoadMore}
                  disabled={isLoading}
                  className="w-full text-xs text-muted-foreground hover:text-foreground"
                >
                  {isLoading ? (
                    <Loader2 className="size-3.5 animate-spin mr-1" />
                  ) : null}
                  Load older chats
                </Button>
              </div>
            )}
          </>
        )}

        {isLoading && conversations.length === 0 && (
          <div className="flex items-center justify-center py-6 text-xs text-muted-foreground gap-2">
            <Loader2 className="size-4 animate-spin" />
            Loading conversations
          </div>
        )}
      </div>
    </SidebarGroup>
  );
}