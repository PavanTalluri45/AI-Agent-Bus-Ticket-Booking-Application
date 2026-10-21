"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { NavHistory } from "@/components/nav-history";
import { NavUser } from "@/components/nav-user";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useConversationsContext } from "@/context/ConversationsContext";

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const {
    conversations,
    isLoading,
    error,
    hasMore,
    loadMore,
    rename,
    remove,
  } = useConversationsContext();

  return (
    <Sidebar variant="inset" {...props}>
      <SidebarHeader className="flex flex-col gap-2 p-3 pb-1">
        {/* App Logo & Brand */}
        <div className="flex items-center justify-between px-1">
          <Link href="/chat" className="flex items-center gap-2">
            <Image
              src="/ai-agent.webp"
              alt="Pavan.AI logo"
              width={32}
              height={32}
              className="size-8 shrink-0 rounded-lg"
            />
            <span className="truncate text-base font-semibold tracking-tight">
              Pavan.AI
            </span>
          </Link>
        </div>

        {/* New Chat Button */}
        <div>
          <Button
            variant="ghost"
            nativeButton={false}
            className="w-full mt-3 justify-start gap-3 h-10 text-sm font-medium shadow-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            render={<Link href="/chat" />}
          >
            <Plus className="size-4 shrink-0 text-muted-foreground" />
            <span>New</span>
          </Button>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <NavHistory
          conversations={conversations}
          isLoading={isLoading}
          error={error}
          hasMore={hasMore}
          onLoadMore={loadMore}
          onRename={rename}
          onDelete={remove}
        />
      </SidebarContent>

      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}
