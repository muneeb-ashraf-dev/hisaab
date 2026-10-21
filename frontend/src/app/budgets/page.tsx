"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, CheckCircle2, Loader2, Pencil, Percent, Plus, Target, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Field, NativeSelect } from "@/components/select-field";
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
import { formatMoney, monthLabel, percent, toNumber } from "@/lib/format";
import { categoriesByType, useApi, useReferenceData, useTrackingPeriod } from "@/lib/hooks";
import type { BudgetProgress } from "@/lib/types";
import { cn } from "@/lib/utils";

const schema = z.object({
  category_id: z.string().optional(),
  amount: z
    .string()
    .min(1, "Enter a budget amount")
    .refine((value) => Number(value) > 0, "Amount must be greater than zero"),
  warning_threshold: z
    .string()
    .refine((value) => Number(value) >= 1 && Number(value) <= 100, "Use 1–100"),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

function monthFromAnchor(anchor: Date): string {
  return `${anchor.getFullYear()}-${String(anchor.getMonth() + 1).padStart(2, "0")}`;
}

export default function BudgetsPage() {
  const { anchor, status } = useTrackingPeriod();
  const { categories } = useReferenceData();
  const [month, setMonth] = useState(monthFromAnchor(anchor));
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<BudgetProgress | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BudgetProgress | null>(null);

  useEffect(() => {
    if (!status.data && !status.error) return;
    setMonth((current) => (current === monthFromAnchor(new Date()) ? monthFromAnchor(anchor) : current));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.data?.baseline_date]);

  const periodStart = `${month}-01`;
  const { data, loading, error, refresh } = useApi<BudgetProgress[]>(
    `/budgets${buildQuery({ period_start: periodStart, include_progress: true })}`
  );

  const expenseCategories = categoriesByType(categories, "expense");
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { category_id: "", amount: "", warning_threshold: "80", notes: "" },
  });

  const openCreate = () => {
    setEditing(null);
    form.reset({ category_id: "", amount: "", warning_threshold: "80", notes: "" });
    setFormOpen(true);
  };

  const openEdit = (budget: BudgetProgress) => {
    setEditing(budget);
    form.reset({
      category_id: budget.category_id ?? "",
      amount: budget.amount,
      warning_threshold: String(budget.warning_threshold),
      notes: budget.notes ?? "",
    });
    setFormOpen(true);
  };

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      category_id: values.category_id || null,
      period_start: periodStart,
      amount: values.amount,
      warning_threshold: Number(values.warning_threshold),
      notes: values.notes || null,
    };
    try {
      if (editing?.budget_id) {
        await api(`/budgets/${editing.budget_id}`, {
          method: "PATCH",
          body: JSON.stringify({
            amount: payload.amount,
            warning_threshold: payload.warning_threshold,
            notes: payload.notes,
            category_id: payload.category_id,
          }),
        });
        toast.success("Budget updated");
      } else {
        await api("/budgets", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Budget created");
      }
      setFormOpen(false);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  });

  const confirmDelete = async () => {
    if (!deleteTarget?.budget_id) return;
    await api(`/budgets/${deleteTarget.budget_id}`, { method: "DELETE" });
    toast.success("Budget deleted");
    refresh();
  };

  const budgets = data ?? [];
  const totalBudget = budgets.reduce((sum, item) => sum + toNumber(item.amount), 0);
  const totalSpent = budgets.reduce((sum, item) => sum + toNumber(item.spent), 0);
  const overCount = budgets.filter((item) => item.utilization_pct > 100).length;
  const overall = budgets.find((item) => !item.category_id);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Planning"
        title="Budgets"
        description="Set one overall envelope and optional per-category limits. Spending is net of refunds and never includes transfers."
        actions={
          <>
            <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 shadow-xs">
              <Input
                type="month"
                value={month}
                onChange={(event) => event.target.value && setMonth(event.target.value)}
                className="h-7 w-[136px] border-0 bg-transparent px-1 text-xs shadow-none focus-visible:ring-0 dark:bg-transparent"
              />
            </div>
            <Button onClick={openCreate}>
              <Plus className="size-4" /> New budget
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={`Budget · ${monthLabel(periodStart)}`} value={formatMoney(totalBudget, { decimals: false })} icon={Target} hint={`${budgets.length} envelopes`} />
        <StatCard label="Spent" value={formatMoney(totalSpent)} icon={Target} tone="negative" hint="Net of refunds" />
        <StatCard
          label="Remaining"
          value={formatMoney(totalBudget - totalSpent)}
          icon={CheckCircle2}
          tone={totalBudget - totalSpent < 0 ? "negative" : "positive"}
          hint={overCount ? `${overCount} envelope${overCount === 1 ? "" : "s"} over` : "All within limit"}
        />
        <StatCard
          label="Overall utilization"
          value={percent(overall?.utilization_pct ?? (totalBudget ? (totalSpent / totalBudget) * 100 : null), 0)}
          icon={Percent}
          tone={overall && overall.utilization_pct >= 100 ? "negative" : "gold"}
          hint={overall ? `Warning at ${overall.warning_threshold}%` : "Uses sum of envelopes"}
        />
      </div>

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {loading ? (
        <LoadingBlock rows={4} />
      ) : budgets.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {budgets.map((budget) => {
            const over = budget.utilization_pct > 100;
            const warning = budget.utilization_pct >= budget.warning_threshold && !over;
            return (
              <div key={budget.budget_id ?? budget.category_name} className="surface flex flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{budget.category_name ?? "Overall budget"}</h3>
                      <Pill
                        className={
                          over
                            ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
                            : warning
                              ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300"
                              : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                        }
                      >
                        {over ? <AlertTriangle className="size-2.5" /> : <CheckCircle2 className="size-2.5" />}
                        {over ? "Over" : warning ? "Warning" : "On track"}
                      </Pill>
                    </div>
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {monthLabel(periodStart)} · warns at {budget.warning_threshold}%
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button size="icon-sm" variant="ghost" title="Edit budget" onClick={() => openEdit(budget)}>
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Delete budget"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(budget)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 flex items-baseline justify-between">
                  <span className="money text-xl font-semibold">{formatMoney(budget.spent)}</span>
                  <span className="money text-xs text-muted-foreground">of {formatMoney(budget.amount, { decimals: false })}</span>
                </div>

                <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      over ? "bg-rose-500" : warning ? "bg-amber-500" : "bg-primary"
                    )}
                    style={{ width: `${Math.min(budget.utilization_pct, 100)}%` }}
                  />
                </div>

                <div className="mt-2 flex items-center justify-between text-[11px]">
                  <span className={cn("font-medium", over ? "text-rose-600" : warning ? "text-amber-600" : "text-emerald-700 dark:text-emerald-400")}>
                    {percent(budget.utilization_pct)} used
                  </span>
                  <span className="money text-muted-foreground">
                    {toNumber(budget.remaining) >= 0
                      ? `${formatMoney(budget.remaining, { decimals: false })} left`
                      : `${formatMoney(Math.abs(toNumber(budget.remaining)), { decimals: false })} over`}
                  </span>
                </div>
                {budget.notes ? <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{budget.notes}</p> : null}
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Target}
          title={`No budgets for ${monthLabel(periodStart)}`}
          description="Start with one overall monthly envelope, then add category limits for groceries, transport and utilities."
          action={
            <Button size="sm" onClick={openCreate}>
              <Plus className="size-3.5" /> Create budget
            </Button>
          }
        />
      )}

      <DefinitionNote>
        Utilization is net spending divided by the envelope amount. Refunds reduce spending in the
        original category. A budget can target one expense category or cover all spending (choose
        “Overall budget”). One budget per category per month is allowed.
      </DefinitionNote>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit budget" : "New budget"}</DialogTitle>
            <DialogDescription>
              {monthLabel(periodStart)} · budgets apply to the whole calendar month.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Scope" htmlFor="budget-category" hint="Leave empty to budget all spending together">
              <NativeSelect
                id="budget-category"
                value={form.watch("category_id") ?? ""}
                onChange={(value) => form.setValue("category_id", value)}
                options={expenseCategories.map((category) => ({ value: category.id, label: category.name }))}
                placeholder="Overall budget"
              />
            </Field>
            <Field label="Amount (PKR)" required htmlFor="budget-amount" error={form.formState.errors.amount?.message}>
              <Input id="budget-amount" type="number" step="0.01" min="0" placeholder="0.00" {...form.register("amount")} />
            </Field>
            <Field label="Warning threshold (%)" htmlFor="budget-threshold" error={form.formState.errors.warning_threshold?.message}>
              <Input id="budget-threshold" type="number" min="1" max="100" {...form.register("warning_threshold")} />
            </Field>
            <Field label="Notes" htmlFor="budget-notes">
              <Textarea id="budget-notes" rows={2} placeholder="Optional" {...form.register("notes")} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create budget"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this budget?"
        description="The envelope will be removed. Transactions and reports are not affected."
        confirmLabel="Delete budget"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}
