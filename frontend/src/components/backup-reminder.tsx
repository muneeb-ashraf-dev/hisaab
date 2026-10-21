"use client";

import { useState } from "react";
import { Database, Download, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { useBackupStatus } from "@/lib/hooks";

export function BackupReminder() {
  const { data, error, backingUp, backupNow } = useBackupStatus();
  const [dismissedChangeAt, setDismissedChangeAt] = useState<string | null>(null);

  if (!data || error || !data.can_backup || !data.backup_needed) return null;

  const changeKey = data.last_change_at ?? "initial";
  if (dismissedChangeAt === changeKey) return null;

  const handleBackup = async () => {
    try {
      const result = await backupNow();
      const transactionCount = result.counts.transactions ?? 0;
      toast.success("Local backup saved", {
        description: `${transactionCount} transactions copied to ${result.target_database} (${formatBytes(result.size_bytes)}).`,
      });
    } catch (backupError) {
      toast.error(errorMessage(backupError));
    }
  };

  return (
    <div className="border-b border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40">
      <div className="mx-auto flex w-full max-w-[1420px] flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 text-amber-900 sm:px-6 lg:px-8 dark:text-amber-200">
        <Database className="size-4 shrink-0" />
        <p className="min-w-0 flex-1 text-xs leading-5">
          <span className="font-semibold">Local backup recommended.</span> {data.message}
          {data.last_change_at ? (
            <span className="text-amber-800/80 dark:text-amber-200/70">
              {" "}
              Latest change: {formatDateTime(data.last_change_at)}.
            </span>
          ) : null}
        </p>
        <Button
          size="sm"
          className="h-8"
          onClick={handleBackup}
          disabled={backingUp || data.backup_running}
        >
          {backingUp || data.backup_running ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Download className="size-3.5" />
          )}
          {backingUp || data.backup_running ? "Backing up…" : "Back up now"}
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="text-amber-900 hover:bg-amber-100 hover:text-amber-950 dark:text-amber-200 dark:hover:bg-amber-900/40"
          onClick={() => setDismissedChangeAt(changeKey)}
          aria-label="Dismiss backup reminder"
        >
          <X className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
