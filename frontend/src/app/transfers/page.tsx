"use client";

import { useMemo, useState } from "react";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Plus,
  Repeat2,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { DateRangePicker } from "@/components/date-range-picker";
import { TransferFormDialog } from "@/components/transfer-form-dialog";
import { Button } from "@/components/ui/button";
import { Field, NativeSelect } from "@/components/select-field";
import {
  DefinitionNote,
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Pill,
  StatCard,
} from "@/components/ui-extras";
import { api, buildQuery, errorMessage } from "@/lib/api";
import { formatDate, formatMoney, toNumber } from "@/lib/format";
import { useApi, useReferenceData, useTrackingPeriod } from "@/lib/hooks";
import type { Page, Transfer } from "@/lib/types";

export default function TransfersPage() {
  const { range, setRange, anchor } = useTrackingPeriod();
  const { accounts } = useReferenceData();
  const [accountId, setAccountId] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Transfer | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Transfer | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const path = range
    ? `/transfers${buildQuery({
        page,
        page_size: pageSize,
        start_date: range.start,
        end_date: range.end,
        account_id: accountId || undefined,
      })}`
    : null;

  const { data, loading, error, refresh } = useApi<Page<Transfer>>(path);

  const totals = useMemo(() => {
    const items = data?.items ?? [];
    const moved = items.reduce((sum, item) => sum + toNumber(item.amount), 0);
    const accountMap = new Map<string, number>();
    for (const item of items) {
      accountMap.set(item.from_account_id, (accountMap.get(item.from_account_id) ?? 0) - toNumber(item.amount));
      accountMap.set(item.to_account_id, (accountMap.get(item.to_account_id) ?? 0) + toNumber(item.amount));
    }
    return { moved, accountMap };
  }, [data]);

  const openNew = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id);
    try {
      await api(`/transfers/${deleteTarget.id}?reason=${encodeURIComponent("Deleted from transfers page")}`, {
        method: "DELETE",
      });
      toast.success("Transfer deleted", { description: "Both account balances were reversed." });
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const meta = data?.meta;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Money"
        title="Transfers"
        description="Move money between salary-M, salary-A and savings. Each transfer is atomic: one side cannot post without the other, and the combined balance never changes."
        actions={
          <>
            {range ? <DateRangePicker value={range} onChange={(next) => { setRange(next); setPage(1); }} anchor={anchor} compact /> : null}
            <Button onClick={openNew}>
              <Plus className="size-4" /> New transfer
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Moved in period"
          value={formatMoney(totals.moved)}
          icon={Repeat2}
          tone="default"
          hint={`${data?.meta.total ?? 0} transfers`}
        />
        <StatCard
          label="Combined balance"
          value={formatMoney(accounts.reduce((sum, account) => sum + toNumber(account.current_balance), 0))}
          icon={Repeat2}
          tone="positive"
          hint="Unchanged by internal transfers"
        />
        <StatCard
          label="Accounts involved"
          value={String(totals.accountMap.size)}
          icon={Repeat2}
          tone="gold"
          hint="Transfers never count as income or expense"
        />
      </div>

      <div className="surface flex flex-wrap items-end gap-3 p-3">
        <Field label="Account" className="w-full sm:w-64">
          <NativeSelect
            value={accountId}
            onChange={(value) => {
              setAccountId(value);
              setPage(1);
            }}
            options={accounts.map((account) => ({ value: account.id, label: account.name }))}
            placeholder="All accounts"
          />
        </Field>
        <p className="pb-2 text-[11px] text-muted-foreground">
          Showing transfers where the account is either the source or destination.
        </p>
      </div>

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      <div className="surface overflow-hidden">
        {loading ? (
          <div className="p-4">
            <LoadingBlock rows={6} />
          </div>
        ) : data?.items.length ? (
          <ul className="divide-y divide-border/60">
            {data.items.map((transfer) => (
              <li
                key={transfer.id}
                className={`group flex flex-col gap-3 px-4 py-3.5 transition-colors hover:bg-muted/25 sm:flex-row sm:items-center ${busyId === transfer.id ? "opacity-60" : ""}`}
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
                  <Repeat2 className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[13px] font-medium">{transfer.description}</p>
                    <Pill className="border-border bg-secondary text-secondary-foreground">Internal</Pill>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className="font-medium text-foreground/80">{transfer.from_account_name}</span>
                    <ArrowRight className="size-3" />
                    <span className="font-medium text-foreground/80">{transfer.to_account_name}</span>
                    <span className="text-border">·</span>
                    <span>{formatDate(transfer.transfer_date)}</span>
                    {transfer.notes ? (
                      <>
                        <span className="text-border">·</span>
                        <span className="truncate">{transfer.notes}</span>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="flex items-center gap-3 sm:justify-end">
                  <span className="money text-sm font-semibold">{formatMoney(transfer.amount)}</span>
                  <div className="flex items-center gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Edit transfer"
                      onClick={() => {
                        setEditing(transfer);
                        setFormOpen(true);
                      }}
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Delete transfer"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(transfer)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="p-5">
            <EmptyState
              icon={Repeat2}
              title="No transfers in this range"
              description="Move money between your own accounts without affecting income, spending or the combined balance."
              action={
                <Button size="sm" onClick={openNew}>
                  <Plus className="size-3.5" /> New transfer
                </Button>
              }
            />
          </div>
        )}

        {meta ? (
          <div className="flex items-center justify-between border-t border-border/70 bg-muted/20 px-4 py-2.5">
            <p className="text-[11px] text-muted-foreground">
              {meta.total} transfer{meta.total === 1 ? "" : "s"}
            </p>
            <div className="flex items-center gap-1">
              <Button
                size="icon-sm"
                variant="outline"
                disabled={meta.page <= 1}
                onClick={() => setPage((value) => Math.max(value - 1, 1))}
                aria-label="Previous page"
              >
                <ChevronLeft className="size-3.5" />
              </Button>
              <span className="px-2 text-[11px] text-muted-foreground">
                {meta.page} / {meta.total_pages}
              </span>
              <Button
                size="icon-sm"
                variant="outline"
                disabled={meta.page >= meta.total_pages}
                onClick={() => setPage((value) => Math.min(value + 1, meta.total_pages))}
                aria-label="Next page"
              >
                <ChevronRight className="size-3.5" />
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <DefinitionNote>
        Transfers are stored as a single row and applied atomically in both directions. Editing or
        deleting one reverses the original movement first, so balances can never drift. Combined
        balance is identical before and after a transfer.
      </DefinitionNote>

      <TransferFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(null);
        }}
        transfer={editing}
        onSaved={refresh}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this transfer?"
        description="Both account balances will be reversed and the transfer will be removed from the ledger."
        confirmLabel="Delete transfer"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}
