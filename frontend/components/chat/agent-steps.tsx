"use client";

import * as React from "react";
import { CircleAlertIcon, CircleCheckIcon, Loader2Icon } from "lucide-react";
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace";
import type { AgentStep } from "@/types/bus-booking";

interface AgentStepsProps {
  steps: AgentStep[];
  /** True while the agent is still working on this reply. */
  streaming?: boolean;
}

function formatDuration(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function StepLine({ step }: { step: AgentStep }) {
  const status =
    step.status === "running"
      ? "running"
      : step.status === "error"
        ? "error"
        : undefined;

  return (
    <TraceLine status={status}>
      <TraceIcon>
        {step.status === "running" ? (
          <Loader2Icon className="animate-spin" />
        ) : step.status === "error" ? (
          <CircleAlertIcon />
        ) : (
          <CircleCheckIcon />
        )}
      </TraceIcon>
      <TraceTitle>{step.title}</TraceTitle>
      {step.description && (
        <TraceDescription className="min-w-0 shrink truncate">
          {step.description}
        </TraceDescription>
      )}
      {step.duration_ms !== undefined && step.status !== "running" && (
        <TraceDescription>{formatDuration(step.duration_ms)}</TraceDescription>
      )}
    </TraceLine>
  );
}

/**
 * Chain of thought for the agent: a summary line that expands into the steps
 * the agent took. Open while the agent works, collapsed once it is done.
 */
export function AgentSteps({ steps, streaming = false }: AgentStepsProps) {
  const [open, setOpen] = React.useState<boolean>();

  if (steps.length === 0) return null;

  const failed = steps.filter((step) => step.status === "error").length;
  const currentStep = [...steps]
    .reverse()
    .find((step) => step.status === "running");

  const title = streaming
    ? (currentStep?.title ?? "Working on it")
    : failed > 0
      ? `Finished with ${failed} failed step${failed === 1 ? "" : "s"}`
      : `Completed in ${steps.length} step${steps.length === 1 ? "" : "s"}`;

  return (
    <Trace>
      <TraceCollapsible open={open ?? streaming} onOpenChange={setOpen}>
        <TraceCollapsibleTrigger>
          <TraceLine
            status={streaming ? "running" : failed > 0 ? "error" : undefined}
          >
            <TraceTitle>{title}</TraceTitle>
          </TraceLine>
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent keepMounted>
          <Trace>
            {steps.map((step) => (
              <StepLine key={step.id} step={step} />
            ))}
          </Trace>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  );
}
