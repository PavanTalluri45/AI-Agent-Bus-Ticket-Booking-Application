"use client";

import React, { useState } from "react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
    <Card className="border-amber-300 dark:border-amber-700 bg-amber-50/70 dark:bg-amber-950/30 shadow-sm mt-3 mb-2">
      <CardHeader className="pb-2 pt-4 px-4">
        <div className="flex items-center gap-2 text-amber-800 dark:text-amber-400">
          <ShieldCheck className="w-5 h-5 flex-shrink-0" />
          <CardTitle className="text-sm font-semibold tracking-wide uppercase">
            Confirmation Required
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="px-4 py-2">
        <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
          {prompt}
        </p>
      </CardContent>
      <CardFooter className="flex items-center justify-end gap-2 px-4 pb-4 pt-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleReject}
          disabled={isBusy}
          className="border-gray-300 hover:bg-red-50 hover:text-red-600 hover:border-red-300 dark:hover:bg-red-950/50"
        >
          {submittingAction === "reject" ? (
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin text-red-500" />
          ) : (
            <X className="w-4 h-4 mr-1.5 text-red-500" />
          )}
          Reject
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={handleApprove}
          disabled={isBusy}
          className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
        >
          {submittingAction === "approve" ? (
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
          ) : (
            <Check className="w-4 h-4 mr-1.5" />
          )}
          Approve & Proceed
        </Button>
      </CardFooter>
    </Card>
  );
}

