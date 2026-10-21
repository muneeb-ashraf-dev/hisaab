"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  BellRing,
  CalendarClock,
  Check,
  Clock3,
  Loader2,
  Pencil,
  Play,
  Plus,
  Repeat,
  SkipForward,
  Trash2,
} from "lucide-react";
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
import { FREQUENCY_LABELS, TXN_LABELS } from "@/lib/constants";
import { formatDate, formatMoney, toNumber } from "@/lib/format";
import { categoriesByType, useApi, useReferenceData } from "@/lib/hooks";
import type { PostDueResult, Recurring, UpcomingRecurring } from "@/lib/types";
import { cn } from "@/lib/utils";
import { TXN_COLORS } from "@/lib/constants";

const schema = z
  .object({
    name: z.string().trim().min(1, "Name the template").max(120),
    transaction_type: z.enum(["income", "expense"]),
    amount: z
      .string()
      .min(1, "Enter an amount")
      .refine((value) => Number(value) > 0, "Amount must be greater than zero"),
    account_id: z.string().min(1, "Choose an account"),
    category_id: z.string().min(1, "Choose a category"),
    description: z.string().trim().min(1, "Add a description").max(255),
    merchant_or_payee: z.string().max(160).optional(),
    payment_method: z.string().max(60).optional(),
    frequency: z.enum(["weekly", "monthly", "quarterly", "yearly"]),
    interval_count: z.string().refine((value) => Number(value) >= 1 && Number(value) <= 12, "Use 1–12"),
    start_date: z.string().min(1, "Choose a start date"),
    next_due_date: z.string().min(1, "Choose the next due date"),
    end_date: z.string().optional(),
    auto_post: z.boolean(),
    is_active: z.boolean(),
    notes: z.string().optional(),
  })
  .refine(
    (values) => !values.end_date || values.end_date >= values.start_date,
    { path: ["end_date"], message: "End date must be on or after the start" }
  );

type FormValues = z.infer<typeof schema>;

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function RecurringPage() {
  const { accounts, categories } = useReferenceData();
  const templates = useApi<Recurring[]>("/recurring");
  const upcoming = useApi<UpcomingRecurring[]>("/recurring/upcoming?horizon_days=45");

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Recurring | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Recurring | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      transaction_type: "expense",
      amount: "",
      account_id: "",
      category_id: "",
      description: "",
      merchant_or_payee: "",
      payment_method: "",
      frequency: "monthly",
      interval_count: "1",
      start_date: todayISO(),
      next_due_date: todayISO(),
      end_date: "",
      auto_post: false,
      is_active: true,
      notes: "",
    },
  });

  const transactionType = form.watch("transaction_type");
  const availableCategories = categoriesByType(categories, transactionType);

  const openCreate = () => {
    setEditing(null);
    form.reset({
      name: "",
      transaction_type: "expense",
      amount: "",
      account_id: accounts[0]?.id ?? "",
      category_id: "",
      description: "",
      merchant_or_payee: "",
      payment_method: "",
      frequency: "monthly",
      interval_count: "1",
      start_date: todayISO(),
      next_due_date: todayISO(),
      end_date: "",
      auto_post: false,
      is_active: true,
      notes: "",
    });
    setFormOpen(true);
  };

  const openEdit = (template: Recurring) => {
    setEditing(template);
    form.reset({
      name: template.name,
      transaction_type: template.transaction_type === "income" ? "income" : "expense",
      amount: template.amount,
      account_id: template.account_id,
      category_id: template.category_id,
      description: template.description,
      merchant_or_payee: template.merchant_or_payee ?? "",
      payment_method: template.payment_method ?? "",
      frequency: template.frequency,
      interval_count: String(template.interval_count),
      start_date: template.start_date,
      next_due_date: template.next_due_date,
      end_date: template.end_date ?? "",
      auto_post: template.auto_post,
      is_active: template.is_active,
      notes: template.notes ?? "",
    });
    setFormOpen(true);
  };

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      transaction_type: values.transaction_type,
      amount: values.amount,
      account_id: values.account_id,
      category_id: values.category_id,
      description: values.description,
      merchant_or_payee: values.merchant_or_payee || null,
      payment_method: values.payment_method || null,
      frequency: values.frequency,
      interval_count: Number(values.interval_count),
      start_date: values.start_date,
      next_due_date: values.next_due_date,
      end_date: values.end_date || null,
      auto_post: values.auto_post,
      is_active: values.is_active,
      notes: values.notes || null,
    };
    try {
      if (editing) {
        await api(`/recurring/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) });
        toast.success("Template updated");
      } else {
        await api("/recurring", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Recurring template created");
      }
      setFormOpen(false);
      templates.refresh();
      upcoming.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  });

  const toggleActive = async (template: Recurring) => {
    setBusy(template.id);
    try {
      await api(`/recurring/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !template.is_active }),
      });
      templates.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const postOccurrence = async (item: UpcomingRecurring) => {
    setBusy(item.template_id);
    try {
      const result = await api<PostDueResult>(
        `/recurring/${item.template_id}/post${buildQuery({ through: item.due_date })}`,
        { method: "POST" }
      );
      toast.success(result.message || "Posted to the ledger");
      templates.refresh();
      upcoming.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const skipOccurrence = async (item: UpcomingRecurring) => {
    setBusy(item.template_id);
    try {
      await api(`/recurring/${item.template_id}/skip${buildQuery({ due_date: item.due_date })}`, {
        method: "POST",
      });
      toast.success("Occurrence skipped");
      templates.refresh();
      upcoming.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const runDue = async () => {
    setRunning(true);
    try {
      const result = await api<PostDueResult>("/recurring/run", { method: "POST" });
      toast.success(result.message || `Posted ${result.created_count} occurrence(s)`);
      templates.refresh();
      upcoming.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRunning(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await api(`/recurring/${deleteTarget.id}`, { method: "DELETE" });
    toast.success("Template deleted", { description: "Already-posted transactions are kept." });
    templates.refresh();
    upcoming.refresh();
  };

  const items = templates.data ?? [];
  const upcomingItems = upcoming.data ?? [];
  const overdue = upcomingItems.filter((item) => item.is_overdue).length;
  const monthlyExpense = items
    .filter((item) => item.transaction_type === "expense" && item.frequency === "monthly")
    .reduce((sum, item) => sum + toNumber(item.amount), 0);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Planning"
        title="Recurring payments"
        description="Templates for salary, rent, utilities and subscriptions — with due reminders and idempotent posting to the ledger."
        actions={
          <>
            <Button variant="outline" onClick={runDue} disabled={running}>
              {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              Post all due
            </Button>
            <Button onClick={openCreate}>
              <Plus className="size-4" /> New template
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Templates" value={String(items.length)} icon={Repeat} hint={`${items.filter((item) => item.is_active).length} active`} />
        <StatCard label="Due in 45 days" value={String(upcomingItems.length)} icon={CalendarClock} tone="gold" hint={`${overdue} overdue`} />
        <StatCard label="Monthly expenses" value={formatMoney(monthlyExpense)} icon={Clock3} tone="negative" hint="From monthly templates" />
        <StatCard
          label="Next due"
          value={upcomingItems.length ? formatDate(upcomingItems[0].due_date, "d MMM") : "—"}
          icon={BellRing}
          hint={upcomingItems[0]?.name ?? "Nothing scheduled"}
        />
      </div>

      {templates.error || upcoming.error ? (
        <ErrorState message={templates.error ?? upcoming.error ?? "Could not load recurring data"} onRetry={() => { templates.refresh(); upcoming.refresh(); }} />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-sm font-semibold">Templates</h2>
            {templates.loading ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" /> : null}
          </div>
          {templates.loading ? (
            <LoadingBlock rows={4} />
          ) : items.length ? (
            <div className="space-y-3">
              {items.map((template) => (
                <div
                  key={template.id}
                  className={cn(
                    "surface flex flex-col gap-3 p-4 sm:flex-row sm:items-center",
                    busy === template.id && "opacity-60",
                    !template.is_active && "opacity-70"
                  )}
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
                    <Repeat className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[13px] font-semibold">{template.name}</p>
                      <Pill className={TXN_COLORS[template.transaction_type]}>
                        {TXN_LABELS[template.transaction_type]}
                      </Pill>
                      {!template.is_active ? <Pill className="border-border bg-muted text-muted-foreground">paused</Pill> : null}
                      {template.auto_post ? <Pill className="border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-300">auto-post</Pill> : null}
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {template.account_name} · {template.category_name} · {FREQUENCY_LABELS[template.frequency]}
                      {template.frequency !== "weekly" && template.interval_count > 1 ? ` every ${template.interval_count}` : ""}
                      {" · "}
                      next {formatDate(template.next_due_date)}
                      {template.end_date ? ` · ends ${formatDate(template.end_date)}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 sm:flex-col sm:items-end">
                    <span className="money text-sm font-semibold">{formatMoney(template.amount)}</span>
                    <div className="flex items-center gap-0.5">
                      <Button size="icon-sm" variant="ghost" title={template.is_active ? "Pause" : "Activate"} onClick={() => toggleActive(template)}>
                        {template.is_active ? <Clock3 className="size-3.5" /> : <Check className="size-3.5" />}
                      </Button>
                      <Button size="icon-sm" variant="ghost" title="Edit template" onClick={() => openEdit(template)}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title="Delete template"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(template)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Repeat}
              title="No recurring templates"
              description="Add rent, utilities or salary to see due reminders and post them in one click."
              action={
                <Button size="sm" onClick={openCreate}>
                  <Plus className="size-3.5" /> New template
                </Button>
              }
            />
          )}
        </div>

        <div className="surface p-4 lg:col-span-5">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-sm font-semibold">Due soon</h2>
              <p className="text-[11px] text-muted-foreground">Next 45 days, including overdue</p>
            </div>
            {upcoming.loading ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" /> : null}
          </div>
          {upcomingItems.length ? (
            <ul className="divide-y divide-border/60">
              {upcomingItems.map((item) => (
                <li key={`${item.template_id}-${item.due_date}`} className="py-3">
                  <div className="flex items-start gap-2.5">
                    <span
                      className={cn(
                        "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg",
                        item.is_overdue
                          ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                          : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                      )}
                    >
                      <CalendarClock className="size-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-xs font-medium">{item.name}</p>
                        <span className="money shrink-0 text-xs font-semibold">{formatMoney(item.amount)}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">
                        {formatDate(item.due_date)} · {item.account_name} · {item.category_name ?? "—"}
                        {item.is_overdue ? " · overdue" : ""}
                      </p>
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={busy === item.template_id}
                          onClick={() => postOccurrence(item)}
                        >
                          <Play className="size-2.5" /> Post
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          disabled={busy === item.template_id}
                          onClick={() => skipOccurrence(item)}
                        >
                          <SkipForward className="size-2.5" /> Skip
                        </Button>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={CalendarClock} title="Nothing due" description="Upcoming occurrences will appear here." />
          )}
        </div>
      </div>

      <DefinitionNote>
        Posting an occurrence creates a normal income or expense transaction and records it against
        the template so the same due date can never post twice. Skipping marks an occurrence without
        touching the ledger. Deleting a template keeps transactions it already created.
      </DefinitionNote>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit recurring template" : "New recurring template"}</DialogTitle>
            <DialogDescription>
              Choose how often this happens and when it is next due. Occurrences post to the same
              account and category each time.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name" required htmlFor="rec-name" error={form.formState.errors.name?.message}>
                <Input id="rec-name" placeholder="e.g. Apartment rent" {...form.register("name")} />
              </Field>
              <Field label="Type" htmlFor="rec-type">
                <NativeSelect
                  id="rec-type"
                  value={transactionType}
                  onChange={(value) => {
                    form.setValue("transaction_type", value as "income" | "expense");
                    form.setValue("category_id", "");
                  }}
                  options={[
                    { value: "expense", label: "Expense" },
                    { value: "income", label: "Income" },
                  ]}
                />
              </Field>
              <Field label="Amount (PKR)" required htmlFor="rec-amount" error={form.formState.errors.amount?.message}>
                <Input id="rec-amount" type="number" step="0.01" min="0" {...form.register("amount")} />
              </Field>
              <Field label="Account" required htmlFor="rec-account">
                <NativeSelect
                  id="rec-account"
                  value={form.watch("account_id")}
                  onChange={(value) => form.setValue("account_id", value, { shouldValidate: true })}
                  options={accounts.filter((account) => account.is_active).map((account) => ({ value: account.id, label: account.name }))}
                  placeholder="Choose account"
                />
              </Field>
              <Field label="Category" required htmlFor="rec-category" error={form.formState.errors.category_id?.message}>
                <NativeSelect
                  id="rec-category"
                  value={form.watch("category_id")}
                  onChange={(value) => form.setValue("category_id", value, { shouldValidate: true })}
                  options={availableCategories.map((category) => ({ value: category.id, label: category.name }))}
                  placeholder="Choose category"
                />
              </Field>
              <Field label="Description" required htmlFor="rec-description" error={form.formState.errors.description?.message}>
                <Input id="rec-description" placeholder="Appears on each transaction" {...form.register("description")} />
              </Field>
              <Field label="Frequency" htmlFor="rec-frequency">
                <NativeSelect
                  id="rec-frequency"
                  value={form.watch("frequency")}
                  onChange={(value) => form.setValue("frequency", value as FormValues["frequency"])}
                  options={Object.entries(FREQUENCY_LABELS).map(([value, label]) => ({ value, label }))}
                />
              </Field>
              <Field label="Every N periods" htmlFor="rec-interval" error={form.formState.errors.interval_count?.message}>
                <Input id="rec-interval" type="number" min="1" max="12" {...form.register("interval_count")} />
              </Field>
              <Field label="Start date" required htmlFor="rec-start">
                <Input id="rec-start" type="date" {...form.register("start_date")} />
              </Field>
              <Field label="Next due" required htmlFor="rec-next">
                <Input id="rec-next" type="date" {...form.register("next_due_date")} />
              </Field>
              <Field label="End date" htmlFor="rec-end" error={form.formState.errors.end_date?.message}>
                <Input id="rec-end" type="date" {...form.register("end_date")} />
              </Field>
              <Field label="Notes" htmlFor="rec-notes">
                <Input id="rec-notes" placeholder="Optional" {...form.register("notes")} />
              </Field>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg border border-border bg-muted/25 px-3 py-2">
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" className="size-3.5 accent-[var(--primary)]" {...form.register("is_active")} />
                Active
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" className="size-3.5 accent-[var(--primary)]" {...form.register("auto_post")} />
                Auto-post when due
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create template"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this template?"
        description="Future occurrences stop. Transactions already posted are kept in the ledger."
        confirmLabel="Delete template"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}
