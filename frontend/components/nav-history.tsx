"use client";

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

export type HistoryItem = {
  id: string;
  title: string;
  url: string;
};

export function NavHistory({ history }: { history: HistoryItem[] }) {
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>History</SidebarGroupLabel>
      {history.length === 0 ? (
        <Empty className="gap-2 border p-4">
          <EmptyHeader>
            <EmptyTitle className="text-sm">No history yet</EmptyTitle>
            <EmptyDescription className="text-xs">
              Your recent bus searches and bookings will appear here.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <SidebarMenu>
          {history.map((item) => (
            <SidebarMenuItem key={item.id}>
              <SidebarMenuButton render={<a href={item.url} />}>
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      )}
    </SidebarGroup>
  );
}
