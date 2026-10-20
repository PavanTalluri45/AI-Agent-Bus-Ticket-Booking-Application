"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import { Check, X, Loader2, ShieldCheck } from "lucide-react";

interface ApprovalCardProps {
  prompt: string;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  disabled?: boolean;
}

export function ApprovalCard({
  prompt,
  onApprove,
  onReject,
  disabled = false,
}: ApprovalCardProps) {
  const [submittingAction, setSubmittingAction] = useState<"approve" | "reject" | null>(null);

  const handleApprove = async () => {
    if (disabled || submittingAction) return;
    setSubmittingAction("approve");
    try {
      await onApprove();
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleReject = async () => {
    if (disabled || submittingAction) return;
    setSubmittingAction("reject");
    try {
      await onReject();
    } finally {
      setSubmittingAction(null);
    }
  };

  const isBusy = disabled || submittingAction !== null;

  return (
    <Item variant="outline" size="sm" className="mt-3 mb-2">
      <ItemMedia variant="icon">
        <ShieldCheck />
      </ItemMedia>
      <ItemContent>
        <ItemTitle>Confirmation required</ItemTitle>
        {/* ItemDescription clamps to 2 lines by default; the agent prompt is a multi-line booking summary */}
        <ItemDescription className="line-clamp-none whitespace-pre-wrap">
          {prompt}
        </ItemDescription>
      </ItemContent>
      <ItemFooter>
        <ItemActions className="ml-auto">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleReject}
            disabled={isBusy}
          >
            {submittingAction === "reject" ? <Loader2 className="animate-spin" /> : <X />}
            Reject
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleApprove}
            disabled={isBusy}
          >
            {submittingAction === "approve" ? <Loader2 className="animate-spin" /> : <Check />}
            Approve &amp; Proceed
          </Button>
        </ItemActions>
      </ItemFooter>
    </Item>
  );
}