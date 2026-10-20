import { BusBookingChat } from "@/components/chat/bus-booking-chat";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return (
    <BusBookingChat key={conversationId} conversationId={conversationId} />
  );
}
