import { Bot, ShieldCheck, Workflow, Ticket } from "lucide-react";

const features = [
  {
    icon: Bot,
    title: "Just tell it where you're going",
    description:
      "Describe your trip in plain language and the assistant works out the right bus for you — no forms to fill in.",
  },
  {
    icon: ShieldCheck,
    title: "Real seats, real prices",
    description:
      "Every seat, fare, and booking status you see is checked against live data, never guessed or made up.",
  },
  {
    icon: Workflow,
    title: "Careful, step-by-step actions",
    description:
      "Searching, holding a seat, and confirming a booking each happen as a separate, verified step, so nothing gets booked by accident.",
  },
  {
    icon: Ticket,
    title: "Hold, book, or cancel anytime",
    description:
      "Reserve a seat while you decide, confirm it when you're ready, or cancel it later — all in the same conversation.",
  },
];

export function Content() {
  return (
    <div className="flex w-full max-w-sm flex-col gap-8 text-foreground">
      <h1 className="text-2xl font-semibold">Bus Ticket AI Agent</h1>
      <div className="flex flex-col gap-6">
        {features.map(({ icon: Icon, title, description }) => (
          <div key={title} className="flex gap-4">
            <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium">{title}</p>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
