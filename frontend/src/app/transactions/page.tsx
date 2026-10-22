"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Loader2,
  Pencil,
  Plus,
  ReceiptText,
  RotateCcw,
  Search,
  Trash2,
  Undo2,
} from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { DateRangePicker } from "@/components/date-range-picker";
import { TransactionFormDialog } from "@/components/transaction-form-dialog";
import { Field, NativeSelect } from "@/components/select-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pill } from "@/components/ui-extras";
import {
  DefinitionNote,
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
} from "@/components/ui-extras";
import { api, buildQuery, downloadCsv, errorMessage } from "@/lib/api";
import { TXN_COLORS, TXN_LABELS } from "@/lib/constants";
import { formatDate, formatMoney } from "@/lib/format";
import { useApi, useDebounced, useReferenceData, useTrackingPeriod } from "@/lib/hooks";
import type { LedgerEntry, Page, Transaction, TransactionDetail, TransactionType } from "@/lib/types";
import { cn } from "@/lib/utils";

type SortKey = "date-desc" | "date-asc" | "amount-desc" | "amount-asc" | "description-asc";

const SORT_OPTIONS: Array<{ value: SortKey; label: string; sortBy: string; sortDir: string }> = [
  { value: "date-desc", label: "Newest first", sortBy: "entry_date", sortDir: "desc" },
  { value: "date-asc", label: "Oldest first", sortBy: "entry_date", sortDir: "asc" },
  { value: "amount-desc", label: "Largest amount", sortBy: "amount", sortDir: "desc" },
  { value: "amount-asc", label: "Smallest amount", sortBy: "amount", sortDir: "asc" },
  { value: "description-asc", label: "Description A–Z", sortBy: "description", sortDir: "asc" },
];

function deletedRow(transaction: Transaction): LedgerEntry {
  return {
    id: transaction.id,
    entry_kind: "transaction",
    entry_date: transaction.transaction_date,
    amount: transaction.amount,
    direction: ["income", "refund", "adjustment_increase"].includes(transaction.transaction_type)
      ? "in"
      : "out",
    transaction_type: transaction.transaction_type,
    description: transaction.description,
    account_id: transaction.account_id,
    account_name: transaction.account_name,
    from_account_id: null,
    from_account_name: null,
    to_account_id: null,
    to_account_name: null,
    category_id: transaction.category_id,
    category_name: transaction.category_name,
    category_color: transaction.category_color,
    committee_id: transaction.committee_id,
    committee_name: transaction.committee_name,
    merchant_or_payee: transaction.merchant_or_payee,
    payment_method: transaction.payment_method,
    notes: transaction.notes,
    related_transaction_id: transaction.related_transaction_id,
    created_at: transaction.created_at,
  };
}

export default function TransactionsPage() {
  const { range, setRange, anchor } = useTrackingPeriod();
  const { accounts, categories } = useReferenceData();

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search, 350);
  const [type, setType] = useState("");
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [sort, setSort] = useState<SortKey>("date-desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [deletedMode, setDeletedMode] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [refundFor, setRefundFor] = useState<Transaction | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LedgerEntry | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<LedgerEntry | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const sortConfig = SORT_OPTIONS.find((option) => option.value === sort) ?? SORT_OPTIONS[0];

  const ledgerPath = useMemo(() => {
    if (!range) return null;
    if (deletedMode) {
      return `/transactions${buildQuery({
        page,
        page_size: pageSize,
        start_date: range.start,
        end_date: range.end,
        account_id: accountId || undefined,
        category_id: categoryId || undefined,
        transaction_type: (type as TransactionType) || undefined,
        search: debouncedSearch || undefined,
        include_deleted: true,
        sort_by: sortConfig.sortBy === "entry_date" ? "transaction_date" : sortConfig.sortBy,
        sort_dir: sortConfig.sortDir,
      })}`;
    }
    return `/ledger${buildQuery({
      page,
      page_size: pageSize,
      start_date: range.start,
      end_date: range.end,
      account_id: accountId || undefined,
      category_id: categoryId || undefined,
      transaction_type: (type as TransactionType) || undefined,
      search: debouncedSearch || undefined,
      sort_by: sortConfig.sortBy,
      sort_dir: sortConfig.sortDir,
    })}`;
  }, [range, deletedMode, page, pageSize, accountId, categoryId, type, debouncedSearch, sortConfig]);

  const ledger = useApi<Page<LedgerEntry>>(ledgerPath);
  const transactions = useApi<Page<Transaction>>(deletedMode ? ledgerPath : null);

  const rows = useMemo<LedgerEntry[]>(() => {
    if (deletedMode) return (transactions.data?.items ?? []).map(deletedRow);
    return ledger.data?.items ?? [];
  }, [deletedMode, ledger.data, transactions.data]);

  const meta = deletedMode ? transactions.data?.meta : ledger.data?.meta;
  const loading = deletedMode ? transactions.loading : ledger.loading;
  const error = deletedMode ? transactions.error : ledger.error;
  const refresh = () => {
    ledger.refresh();
    transactions.refresh();
  };

  const resetFilters = () => {
    setSearch("");
    setType("");
    setAccountId("");
    setCategoryId("");
    setSort("date-desc");
    setPage(1);
  };

  const openNew = () => {
    setEditing(null);
    setRefundFor(null);
    setFormOpen(true);
  };

  const openEdit = async (entry: LedgerEntry) => {
    if (entry.entry_kind !== "transaction") return;
    setBusyId(entry.id);
    try {
      const detail = await api<TransactionDetail>(`/transactions/${entry.id}`);
      setEditing(detail.transaction);
      setRefundFor(null);
      setFormOpen(true);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const openRefund = async (entry: LedgerEntry) => {
    if (entry.entry_kind !== "transaction" || entry.transaction_type !== "expense") return;
    setBusyId(entry.id);
    try {
      const detail = await api<TransactionDetail>(`/transactions/${entry.id}`);
      setEditing(null);
      setRefundFor(detail.transaction);
      setFormOpen(true);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await api(`/transactions/${deleteTarget.id}?reason=${encodeURIComponent("Deleted from transactions page")}`, {
      method: "DELETE",
    });
    toast.success("Transaction deleted", { description: "Its balance effect was reversed." });
    refresh();
  };

  const confirmRestore = async () => {
    if (!restoreTarget) return;
    await api(`/transactions/${restoreTarget.id}/restore`, { method: "POST" });
    toast.success("Transaction restored");
    refresh();
  };

  const exportCsv = async () => {
    if (!range) return;
    setExporting(true);
    try {
      await downloadCsv(
        `/exports/transactions.csv${buildQuery({
          start_date: range.start,
          end_date: range.end,
          account_id: accountId || undefined,
        })}`,
        "transactions-export.csv"
      );
      toast.success("CSV export started");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  const pageNumbers = useMemo(() => {
    if (!meta) return [];
    const total = meta.total_pages;
    const current = meta.page;
    const start = Math.max(1, Math.min(current - 2, total - 4));
    const end = Math.min(total, start + 4);
    return Array.from({ length: Math.max(end - start + 1, 0) }, (_, index) => start + index);
  }, [meta]);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Money"
        title="Transactions"
        description="Search, filter and reconcile every movement. Transfers appear in the same ledger but are never treated as spending."
        actions={
          <>
            <Button variant="outline" onClick={exportCsv} disabled={exporting}>
              {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
              Export
            </Button>
            <Button onClick={openNew}>
              <Plus className="size-4" /> New transaction
            </Button>
          </>
        }
      />

      <div className="surface p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search description, merchant, notes…"
              className="h-9 pl-8"
            />
          </div>
          {range ? <DateRangePicker value={range} onChange={(next) => { setRange(next); setPage(1); }} anchor={anchor} compact /> : null}
          <Button
            variant={deletedMode ? "secondary" : "outline"}
            onClick={() => {
              setDeletedMode((value) => !value);
              setPage(1);
            }}
          >
            <Undo2 className="size-3.5" /> {deletedMode ? "Viewing deleted" : "Deleted"}
          </Button>
        </div>

        <div className="mt-3 grid gap-2 border-t border-border/70 pt-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Type">
            <NativeSelect
              value={type}
              onChange={(value) => {
                setType(value);
                setPage(1);
              }}
              options={Object.entries(TXN_LABELS).map(([value, label]) => ({ value, label }))}
              placeholder="All types"
            />
          </Field>
          <Field label="Account">
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
          <Field label="Category">
            <NativeSelect
              value={categoryId}
              onChange={(value) => {
                setCategoryId(value);
                setPage(1);
              }}
              options={categories.map((category) => ({ value: category.id, label: category.name }))}
              placeholder="All categories"
            />
          </Field>
          <Field label="Sort">
            <NativeSelect
              value={sort}
              onChange={(value) => {
                setSort(value as SortKey);
                setPage(1);
              }}
              options={SORT_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
            />
          </Field>
          <div className="flex items-end gap-2">
            <Field label="Rows" className="w-20">
              <NativeSelect
                value={String(pageSize)}
                onChange={(value) => {
                  setPageSize(Number(value));
                  setPage(1);
                }}
                options={[10, 20, 50, 100].map((size) => ({ value: String(size), label: String(size) }))}
              />
            </Field>
            <Button variant="ghost" size="sm" onClick={resetFilters} className="mb-0.5">
              <Filter className="size-3.5" /> Reset
            </Button>
          </div>
        </div>
      </div>

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      <div className="surface overflow-hidden">
        {loading ? (
          <div className="p-4">
            <LoadingBlock rows={7} />
          </div>
        ) : rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-border/70 bg-muted/30 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Date</th>
                  <th className="px-4 py-2.5 font-medium">Description</th>
                  <th className="px-4 py-2.5 font-medium">Category</th>
                  <th className="px-4 py-2.5 font-medium">Account</th>
                  <th className="px-4 py-2.5 font-medium">Type</th>
                  <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                  <th className="w-28 px-4 py-2.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {rows.map((row) => {
                  const isTransfer = row.entry_kind === "transfer";
                  const typeLabel = isTransfer ? "Transfer" : TXN_LABELS[row.transaction_type ?? ""] ?? "Entry";
                  const badgeClass = isTransfer
                    ? "border-border bg-secondary text-secondary-foreground"
                    : TXN_COLORS[row.transaction_type ?? ""] ?? "border-border bg-secondary";
                  return (
                    <tr key={`${row.entry_kind}-${row.id}`} className={cn("group transition-colors hover:bg-muted/25", busyId === row.id && "opacity-60")}>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {formatDate(row.entry_date)}
                      </td>
                      <td className="max-w-[260px] px-4 py-3">
                        <p className="truncate text-[13px] font-medium text-foreground">{row.description}</p>
                        <p className="truncate text-[10px] text-muted-foreground">
                          {row.merchant_or_payee || row.notes || (isTransfer ? "Internal transfer" : "—")}
                        </p>
                        {row.committee_name ? (
                          <p className="truncate text-[10px] text-emerald-700 dark:text-emerald-300">
                            Committee: {row.committee_name}
                          </p>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {isTransfer ? (
                          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                            <ArrowLeftRight className="size-3" /> Internal
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="size-2 rounded-full" style={{ background: row.category_color ?? "#94A3B8" }} />
                            <span className="text-muted-foreground">{row.category_name ?? "Uncategorized"}</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {isTransfer
                          ? `${row.from_account_name ?? "—"} → ${row.to_account_name ?? "—"}`
                          : row.account_name ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Pill className={badgeClass}>{typeLabel}</Pill>
                      </td>
                      <td
                        className={cn(
                          "money whitespace-nowrap px-4 py-3 text-right text-[13px] font-semibold",
                          row.direction === "in" ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"
                        )}
                      >
                        {row.direction === "in" ? "+" : "−"}
                        {formatMoney(row.amount, { currency: false })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
                          {deletedMode ? (
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              title="Restore"
                              onClick={() => setRestoreTarget(row)}
                            >
                              <RotateCcw className="size-3.5" />
                            </Button>
                          ) : isTransfer ? (
                            <Button size="icon-sm" variant="ghost" title="Open transfers" nativeButton={false} render={<Link href="/transfers" />}>
                              <ArrowLeftRight className="size-3.5" />
                            </Button>
                          ) : (
                            <>
                              <Button size="icon-sm" variant="ghost" title="Edit" onClick={() => openEdit(row)}>
                                <Pencil className="size-3.5" />
                              </Button>
                              {row.transaction_type === "expense" ? (
                                <Button size="icon-sm" variant="ghost" title="Refund this expense" onClick={() => openRefund(row)}>
                                  <Undo2 className="size-3.5" />
                                </Button>
                              ) : null}
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                title="Delete"
                                className="text-destructive hover:text-destructive"
                                onClick={() => setDeleteTarget(row)}
                              >
                                <Trash2 className="size-3.5" />
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-5">
            <EmptyState
              icon={ReceiptText}
              title={deletedMode ? "No deleted transactions in this range" : "No entries match these filters"}
              description={
                deletedMode
                  ? "Deleted entries keep their audit trail and can be restored from here."
                  : "Try widening the date range, clearing filters, or recording a new transaction."
              }
              action={
                <Button size="sm" onClick={openNew}>
                  <Plus className="size-3.5" /> New transaction
                </Button>
              }
            />
          </div>
        )}

        {meta ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 bg-muted/20 px-4 py-2.5">
            <p className="text-[11px] text-muted-foreground">
              {meta.total === 0
                ? "No entries"
                : `${(meta.page - 1) * meta.page_size + 1}–${Math.min(meta.page * meta.page_size, meta.total)} of ${meta.total}`}
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
              {pageNumbers.map((number) => (
                <Button
                  key={number}
                  size="sm"
                  variant={number === meta.page ? "default" : "ghost"}
                  onClick={() => setPage(number)}
                  className="min-w-8"
                >
                  {number}
                </Button>
              ))}
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
        Deleting a transaction is reversible: its balance effect is reversed immediately and the row
        is retained with an audit trail. Refunds stay linked to the original expense and reduce net
        spending in reports.
      </DefinitionNote>

      <TransactionFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditing(null);
            setRefundFor(null);
          }
        }}
        transaction={editing}
        defaultType={refundFor ? "refund" : "expense"}
        defaultRelatedId={refundFor?.id}
        defaultAccountId={refundFor?.account_id}
        onSaved={refresh}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this transaction?"
        description="The account balance will be adjusted back. The row is soft-deleted and can be restored later."
        confirmLabel="Delete transaction"
        destructive
        onConfirm={confirmDelete}
      />
      <ConfirmDialog
        open={Boolean(restoreTarget)}
        onOpenChange={(open) => !open && setRestoreTarget(null)}
        title="Restore this transaction?"
        description="Its original balance effect will be applied again, and it will reappear in reports."
        confirmLabel="Restore"
        onConfirm={confirmRestore}
      />
    </div>
  );
}
