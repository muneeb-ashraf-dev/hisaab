"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CalendarRange,
  CheckCircle2,
  CircleAlert,
  CircleDollarSign,
  HandCoins,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Wallet,
} from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Field } from "@/components/select-field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
import { formatDate, formatMoney, monthStartISO, toNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Committee } from "@/lib/types";
import { cn } from "@/lib/utils";

const committeeSchema = z
  .object({
    name: z.string().trim().min(1, "Name the committee").max(120),
    monthly_amount: z
      .string()
      .min(1, "Enter the monthly installment")
      .refine((value) => Number(value) > 0, "Installment must be greater than zero"),
    start_month: z.string().regex(/^\d{4}-\d{2}$/, "Choose a start month"),
    end_month: z.string().regex(/^\d{4}-\d{2}$/, "Choose an end month"),
    prior_paid_installments: z
      .string()
      .regex(/^\d+$/, "Enter a whole number")
      .refine((value) => Number(value) >= 0, "Cannot be negative"),
    notes: z.string().optional(),
  })
  .refine((values) => values.end_month >= values.start_month, {
    message: "End month must be on or after the start month",
    path: ["end_month"],
  })
  .superRefine((values, ctx) => {
    const total = monthCount(values.start_month, values.end_month);
    if (Number(values.prior_paid_installments) > total) {
      ctx.addIssue({
        code: "custom",
        path: ["prior_paid_installments"],
        message: "Already paid cannot exceed the total installments",
      });
    }
  });

type CommitteeValues = z.infer<typeof committeeSchema>;

const STATUS_STYLES: Record<string, string> = {
  active:
    "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  upcoming:
    "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-300",
  completed:
    "border-border bg-muted text-muted-foreground",
};

function currentMonthInput(): string {
  return monthStartISO().slice(0, 7);
}

function monthInputToDate(value: string): string {
  return `${value}-01`;
}

function monthCount(start: string, end: string): number {
  if (!/^\d{4}-\d{2}$/.test(start) || !/^\d{4}-\d{2}$/.test(end) || end < start) {
    return 0;
  }
  const [startYear, startMonth] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);
  return (endYear - startYear) * 12 + (endMonth - startMonth) + 1;
}

function committeeStatus(committee: Committee): "active" | "upcoming" | "completed" {
  if (committee.current_month < committee.start_month) return "upcoming";
  if (committee.current_month > committee.end_month) return "completed";
  return "active";
}

export default function CommitteesPage() {
  const [asOfMonth, setAsOfMonth] = useState(currentMonthInput);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Committee | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Committee | null>(null);

  const query = buildQuery({ as_of: monthInputToDate(asOfMonth) });
  const { data, loading, error, refresh } = useApi<Committee[]>(`/committees${query}`);

  useEffect(() => {
    const onDataChanged = () => refresh();
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("hisaab:data-changed", onDataChanged);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("hisaab:data-changed", onDataChanged);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refresh]);

  const form = useForm<CommitteeValues>({
    resolver: zodResolver(committeeSchema),
    defaultValues: {
      name: "",
      monthly_amount: "",
      start_month: currentMonthInput(),
      end_month: currentMonthInput(),
      prior_paid_installments: "0",
      notes: "",
    },
  });

  const watchedStart = useWatch({ control: form.control, name: "start_month" });
  const watchedEnd = useWatch({ control: form.control, name: "end_month" });
  const watchedAmount = useWatch({ control: form.control, name: "monthly_amount" });
  const watchedPriorPaid = useWatch({
    control: form.control,
    name: "prior_paid_installments",
  });
  const draftMonths = useMemo(
    () => monthCount(watchedStart, watchedEnd),
    [watchedStart, watchedEnd]
  );
  const draftPriorPaid = Math.min(
    Math.max(Number(watchedPriorPaid) || 0, 0),
    draftMonths
  );
  const draftTotal = draftMonths * toNumber(watchedAmount);

  const committees = data ?? [];
  const active = committees.filter((committee) => committeeStatus(committee) === "active");
  const monthlyCommitment = active.reduce(
    (sum, committee) => sum + toNumber(committee.monthly_amount),
    0
  );
  const totalPaid = committees.reduce(
    (sum, committee) => sum + toNumber(committee.total_paid),
    0
  );
  const remaining = committees.reduce(
    (sum, committee) => sum + toNumber(committee.remaining_amount),
    0
  );
  const paidInstallments = committees.reduce(
    (sum, committee) => sum + committee.paid_installments,
    0
  );
  const remainingInstallments = committees.reduce(
    (sum, committee) => sum + committee.remaining_installments,
    0
  );

  const openCreate = () => {
    setEditing(null);
    form.reset({
      name: "",
      monthly_amount: "",
      start_month: currentMonthInput(),
      end_month: currentMonthInput(),
      prior_paid_installments: "0",
      notes: "",
    });
    setOpen(true);
  };

  const openEdit = (committee: Committee) => {
    setEditing(committee);
    form.reset({
      name: committee.name,
      monthly_amount: committee.monthly_amount,
      start_month: committee.start_month.slice(0, 7),
      end_month: committee.end_month.slice(0, 7),
      prior_paid_installments: String(committee.prior_paid_installments),
      notes: committee.notes ?? "",
    });
    setOpen(true);
  };

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name.trim(),
      monthly_amount: values.monthly_amount,
      start_month: monthInputToDate(values.start_month),
      end_month: monthInputToDate(values.end_month),
      prior_paid_installments: Number(values.prior_paid_installments),
      notes: values.notes?.trim() || null,
    };
    try {
      if (editing) {
        await api(`/committees/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Committee updated");
      } else {
        await api("/committees", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Committee created");
      }
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  });

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api(`/committees/${deleteTarget.id}`, { method: "DELETE" });
      toast.success("Committee deleted");
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Planning"
        title="Committees"
        description="Plan monthly committee installments and track what has been paid. Expense transactions linked to a committee update its paid months; the plan itself never changes balances."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
              As of
              <Input
                type="month"
                value={asOfMonth}
                onChange={(event) => setAsOfMonth(event.target.value || currentMonthInput())}
                className="h-8 w-[140px]"
              />
            </label>
            <Button onClick={openCreate}>
              <Plus className="size-4" /> New committee
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active plans"
          value={String(active.length)}
          icon={HandCoins}
          hint={`${committees.length} total plan${committees.length === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Monthly commitment"
          value={formatMoney(monthlyCommitment, { decimals: false })}
          icon={Wallet}
          tone="gold"
          hint="Active plans only"
        />
        <StatCard
          label="Paid through selected month"
          value={formatMoney(totalPaid)}
          icon={CircleDollarSign}
          tone="positive"
          hint={`${paidInstallments} installment${paidInstallments === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Remaining"
          value={formatMoney(remaining)}
          icon={CalendarRange}
          hint={`${remainingInstallments} installment${remainingInstallments === 1 ? "" : "s"} left`}
        />
      </div>

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {loading ? (
        <LoadingBlock rows={4} />
      ) : committees.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {committees.map((committee) => {
            const status = committeeStatus(committee);
            const progress = Math.min(committee.progress_pct, 100);
            return (
              <div key={committee.id} className="surface flex flex-col p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-semibold">{committee.name}</h3>
                      <Pill className={STATUS_STYLES[status]}>
                        {status === "active"
                          ? "Active"
                          : status === "upcoming"
                            ? "Upcoming"
                            : "Completed"}
                      </Pill>
                      <Pill className="border-border bg-muted text-muted-foreground">
                        {committee.total_installments} installments
                      </Pill>
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {formatDate(committee.start_month, "MMM yyyy")} to{" "}
                      {formatDate(committee.end_month, "MMM yyyy")}
                    </p>
                    {committee.prior_paid_installments > 0 ||
                    committee.linked_paid_installments > 0 ? (
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        {committee.prior_paid_installments > 0
                          ? `${committee.prior_paid_installments} recorded before tracking`
                          : ""}
                        {committee.prior_paid_installments > 0 &&
                        committee.linked_paid_installments > 0
                          ? " + "
                          : ""}
                        {committee.linked_paid_installments > 0
                          ? `${committee.linked_paid_installments} linked expense${committee.linked_paid_installments === 1 ? "" : "s"}`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Edit committee"
                      onClick={() => openEdit(committee)}
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Delete committee"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(committee)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 flex items-baseline justify-between gap-2">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Monthly installment
                    </p>
                    <p className="money mt-1 text-xl font-semibold">
                      {formatMoney(committee.monthly_amount)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Total
                    </p>
                    <p className="money mt-1 text-sm font-medium">
                      {formatMoney(committee.total_amount, { decimals: false })}
                    </p>
                  </div>
                </div>

                <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      status === "completed" ? "bg-emerald-500" : "bg-primary"
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between gap-2 text-[11px]">
                  <span className="font-medium text-primary">
                    {committee.paid_installments} of {committee.total_installments} paid
                    {" "}
                    ({committee.progress_pct.toFixed(1)}%)
                  </span>
                  <span className="text-muted-foreground">
                    through {formatDate(committee.current_month, "MMM yyyy")}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-emerald-200/70 bg-emerald-50/50 p-2.5 dark:border-emerald-900 dark:bg-emerald-950/30">
                    <p className="flex items-center gap-1 text-[10px] uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-300">
                      <CheckCircle2 className="size-3" /> Paid
                    </p>
                    <p className="money mt-1 text-sm font-semibold text-emerald-800 dark:text-emerald-300">
                      {formatMoney(committee.total_paid, { decimals: false })}
                    </p>
                  </div>
                  <div className="rounded-lg border border-amber-200/70 bg-amber-50/50 p-2.5 dark:border-amber-900 dark:bg-amber-950/30">
                    <p className="flex items-center gap-1 text-[10px] uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">
                      <CircleAlert className="size-3" /> Remaining
                    </p>
                    <p className="money mt-1 text-sm font-semibold text-amber-800 dark:text-amber-300">
                      {formatMoney(committee.remaining_amount, { decimals: false })}
                    </p>
                  </div>
                </div>

                {committee.notes ? (
                  <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
                    {committee.notes}
                  </p>
                ) : null}

                <details className="mt-3 border-t border-border/60 pt-2.5">
                  <summary className="cursor-pointer text-[11px] font-medium text-muted-foreground hover:text-foreground">
                    View month-by-month schedule
                  </summary>
                  <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-border/70">
                    {committee.schedule.map((item) => (
                      <div
                        key={item.month}
                        className={cn(
                          "flex items-center gap-2 border-b border-border/50 px-2.5 py-1.5 text-[11px] last:border-b-0",
                          item.is_current && "bg-amber-50/70 dark:bg-amber-950/20"
                        )}
                      >
                        <span className="w-20 shrink-0 text-muted-foreground">
                          {formatDate(item.month, "MMM yyyy")}
                        </span>
                        <span className="w-10 text-muted-foreground">#{item.installment_number}</span>
                        <span
                          className="money flex-1 text-right"
                          title={
                            item.source === "transaction"
                              ? `Linked expense: ${formatMoney(item.paid_amount)}`
                              : undefined
                          }
                        >
                          {formatMoney(item.amount, { decimals: false })}
                        </span>
                        <Pill
                          className={cn(
                            "min-w-[62px] justify-center",
                            item.status === "paid"
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                              : "border-border bg-muted text-muted-foreground"
                          )}
                        >
                          {item.status === "paid"
                            ? "Paid"
                            : item.is_current
                              ? "Current"
                              : "Upcoming"}
                        </Pill>
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={HandCoins}
          title="No committees yet"
          description="Add a monthly committee plan with its start month, end month and installment amount. Record historical installments as already paid, then link future committee expenses to update the plan automatically."
          action={
            <Button size="sm" onClick={openCreate}>
              <Plus className="size-3.5" /> Create first committee
            </Button>
          }
        />
      )}

      <DefinitionNote>
        Paid months come from installments marked as already paid and from expense transactions
        linked to the committee. Only the linked expense changes an account balance; the committee
        plan itself never creates transactions or transfers. Use the selected month to review the
        plan at an earlier point in time.
      </DefinitionNote>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit committee" : "New committee"}</DialogTitle>
            <DialogDescription>
              Enter the plan period and monthly installment. If the committee started before you
              began using Hisaab, record those installments as already paid. Future payments can be
              linked to this plan from the transaction form.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <Field
              label="Name"
              required
              htmlFor="committee-name"
              error={form.formState.errors.name?.message}
            >
              <Input
                id="committee-name"
                placeholder="e.g. Monthly committee 2026"
                {...form.register("name")}
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Starting month"
                required
                htmlFor="committee-start"
                error={form.formState.errors.start_month?.message}
              >
                <Input id="committee-start" type="month" {...form.register("start_month")} />
              </Field>
              <Field
                label="Ending month"
                required
                htmlFor="committee-end"
                error={form.formState.errors.end_month?.message}
              >
                <Input id="committee-end" type="month" {...form.register("end_month")} />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Monthly installment (PKR)"
                required
                htmlFor="committee-amount"
                error={form.formState.errors.monthly_amount?.message}
              >
                <Input
                  id="committee-amount"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  {...form.register("monthly_amount")}
                />
              </Field>
              <Field
                label="Installments already paid"
                htmlFor="committee-prior-paid"
                error={form.formState.errors.prior_paid_installments?.message}
                hint="Historical months paid before you started tracking. Future payments can be linked from transactions."
              >
                <Input
                  id="committee-prior-paid"
                  type="number"
                  step="1"
                  min="0"
                  max={draftMonths || undefined}
                  {...form.register("prior_paid_installments")}
                />
              </Field>
            </div>
            <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2.5 text-xs">
              {draftMonths > 0 ? (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-muted-foreground">
                    {draftMonths} monthly installment{draftMonths === 1 ? "" : "s"}
                  </span>
                  <span className="money font-semibold">
                    Total {formatMoney(draftTotal, { decimals: false })}
                  </span>
                </div>
              ) : (
                <span className="text-muted-foreground">
                  Choose an ending month on or after the starting month.
                </span>
              )}
              {draftMonths > 0 && draftPriorPaid > 0 ? (
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {draftPriorPaid} of {draftMonths} already paid (
                  {formatMoney(draftPriorPaid * toNumber(watchedAmount), { decimals: false })}).
                </p>
              ) : null}
            </div>
            <Field label="Notes" htmlFor="committee-notes">
              <Textarea
                id="committee-notes"
                rows={2}
                placeholder="Optional"
                {...form.register("notes")}
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create committee"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(value) => !value && setDeleteTarget(null)}
        title="Delete this committee plan?"
        description={
          deleteTarget
            ? `${deleteTarget.name} will be removed. Linked expense transactions stay in the ledger but are unlinked from this plan.`
            : ""
        }
        confirmLabel="Delete committee"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}
