"use client"

import * as React from "react"
import Image from "next/image"
import { NavHistory, type HistoryItem } from "@/components/nav-history"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"

// No history source exists yet — replace with real data when available
const history: HistoryItem[] = []

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar variant="inset" {...props}>
      <SidebarHeader className="h-14 justify-center py-0">
        <div className="flex items-center gap-2 px-2">
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
        </div>
      </SidebarHeader>
      <SidebarContent>
        <NavHistory history={history} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  )
}