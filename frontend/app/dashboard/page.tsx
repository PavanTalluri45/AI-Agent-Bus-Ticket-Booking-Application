import { AppSidebar } from "@/components/app-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { BusBookingChat } from "@/components/chat/bus-booking-chat";

export default function Page() {
  return (
    <SidebarProvider className="has-data-[variant=inset]:bg-transparent">
      <AppSidebar />
      <SidebarInset className="bg-transparent">
        <header className="flex h-14 shrink-0 items-center gap-2 px-4">
          <div className="flex items-center gap-2">
            <SidebarTrigger className="-ml-1" />
          </div>
        </header>

        <main className="flex-1 p-3 sm:p-5">
          <BusBookingChat />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}