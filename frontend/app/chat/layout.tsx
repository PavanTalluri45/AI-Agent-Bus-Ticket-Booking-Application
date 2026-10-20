import React from "react";
import { AppSidebar } from "@/components/app-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ConversationsProvider } from "@/context/ConversationsContext";
import { TooltipProvider } from "@/components/ui/tooltip";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ConversationsProvider>
      <TooltipProvider delay={100}>
        <SidebarProvider className="has-data-[variant=inset]:bg-transparent">
          <AppSidebar />
          <SidebarInset className="bg-transparent flex flex-col h-screen overflow-hidden">
            <header className="flex h-14 shrink-0 items-center gap-2 px-4">
              <SidebarTrigger className="-ml-1" />
            </header>
            <main className="flex-1 overflow-hidden p-3 sm:p-5">
              {children}
            </main>
          </SidebarInset>
        </SidebarProvider>
      </TooltipProvider>
    </ConversationsProvider>
  );
}
