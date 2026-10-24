"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  MoreHorizontal,
  Trash2,
  Loader2,
} from "lucide-react";
import type { ConversationListItem } from "@/types/bus-booking";

export interface NavHistoryProps {
  conversations: ConversationListItem[];
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  onLoadMore: () => Promise<void>;
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
  error,
  hasMore,
  onLoadMore,
  onDelete,
}: NavHistoryProps) {
  const params = useParams();
  const router = useRouter();
  const activeConversationId = params?.conversationId as string | undefined;
  const historyScrollRef = useRef<HTMLDivElement>(null);
  const loadMoreSentinelRef = useRef<HTMLDivElement>(null);
  const isLoadingMoreRef = useRef(false);

  // Delete confirmation state. The target is kept after closing so the
  // title doesn't blank out during the dialog's close animation.
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ConversationListItem | null>(
    null,
  );
  const [isDeleting, setIsDeleting] = useState(false);

  const loadMore = useCallback(async () => {
    if (isLoading || !hasMore || isLoadingMoreRef.current) return;

    isLoadingMoreRef.current = true;
    try {
      await onLoadMore();
    } finally {
      isLoadingMoreRef.current = false;
    }
  }, [hasMore, isLoading, onLoadMore]);

  useEffect(() => {
    const root = historyScrollRef.current;
    const sentinel = loadMoreSentinelRef.current;
    if (!root || !sentinel || !hasMore || error) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void loadMore();
      },
      { root, rootMargin: "120px 0px", threshold: 0 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [error, hasMore, loadMore]);

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

  const openDeleteDialog = (item: ConversationListItem) => {
    setDeleteTarget(item);
    setIsDeleteDialogOpen(true);
  };

  // Block closing (Esc / backdrop / cancel) while the delete is running.
  const handleDialogOpenChange = (open: boolean) => {
    if (isDeleting) return;
    setIsDeleteDialogOpen(open);
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget || isDeleting) return;

    setIsDeleting(true);
    try {
      await onDelete(deleteTarget.id);
      if (activeConversationId === deleteTarget.id) {
        router.push("/chat");
      }
      setIsDeleteDialogOpen(false);
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    } finally {
      setIsDeleting(false);
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
                        title={item.title}
                        aria-label={item.title}
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
                      onClick={() => openDeleteDialog(item)}
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
    <>
      <SidebarGroup className="group-data-[collapsible=icon]:hidden min-h-0 flex-1 px-2 space-y-2">
        <div className="flex items-center justify-between px-2 pt-1">
          <SidebarGroupLabel className="p-0 text-xs font-semibold text-muted-foreground">
            Recent Chats
          </SidebarGroupLabel>
        </div>

        <div
          ref={historyScrollRef}
          className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain scroll-smooth pr-1"
        >
          {conversations.length === 0 && isLoading ? (
            <div className="flex items-center justify-center py-6 text-xs text-muted-foreground gap-2">
              <Loader2 className="size-4 animate-spin" />
              Loading conversations
            </div>
          ) : conversations.length === 0 && error ? (
            <div role="alert" className="px-2 py-4 text-center text-xs text-destructive">
              {error}
            </div>
          ) : conversations.length === 0 ? (
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

              {error && (
                <div role="alert" className="px-2 py-2 text-xs text-destructive">
                  {error}
                </div>
              )}

              {hasMore && (
                <div
                  ref={loadMoreSentinelRef}
                  aria-hidden="true"
                  className="flex min-h-8 items-center justify-center py-2"
                >
                  {isLoading && (
                    <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </SidebarGroup>

      {/* Single delete confirmation dialog, outside the list so it survives
          the item being removed from the sidebar */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={handleDialogOpenChange}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete chat?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this {deleteTarget?.title} chat?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={isDeleting}
            >
              {isDeleting && <Spinner />}
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}