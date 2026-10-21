"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CircleDollarSign,
  Flag,
  Loader2,
  Pencil,
  Plus,
  Target,
  Trash2,
  Trophy,
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
import { api, errorMessage } from "@/lib/api";
import { GOAL_STATUS_LABELS } from "@/lib/constants";
import { formatDate, formatMoney, percent, toNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Goal, GoalStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const goalSchema = z.object({
  name: z.string().trim().min(1, "Name the goal").max(120),
  target_amount: z
    .string()
    .min(1, "Enter a target")
    .refine((value) => Number(value) > 0, "Target must be greater than zero"),
  target_date: z.string().optional(),
  status: z.enum(["active", "completed", "paused", "cancelled"]),
  notes: z.string().optional(),
});

const contributionSchema = z.object({
  amount: z
    .string()
    .min(1, "Enter an amount")
    .refine((value) => Number(value) > 0, "Amount must be greater than zero"),
  contribution_date: z.string().min(1, "Choose a date"),
  note: z.string().optional(),
});

type GoalValues = z.infer<typeof goalSchema>;
type ContributionValues = z.infer<typeof contributionSchema>;

const STATUS_STYLES: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  completed: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-300",
  paused: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
  cancelled: "border-border bg-muted text-muted-foreground",
};

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function GoalsPage() {
  const { data, loading, error, refresh } = useApi<Goal[]>("/goals");
  const [goalOpen, setGoalOpen] = useState(false);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [contributionFor, setContributionFor] = useState<Goal | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Goal | null>(null);
  const [deleteContribution, setDeleteContribution] = useState<{ goal: Goal; id: string } | null>(null);

  const goalForm = useForm<GoalValues>({
    resolver: zodResolver(goalSchema),
    defaultValues: { name: "", target_amount: "", target_date: "", status: "active", notes: "" },
  });
  const contributionForm = useForm<ContributionValues>({
    resolver: zodResolver(contributionSchema),
    defaultValues: { amount: "", contribution_date: todayISO(), note: "" },
  });

  const openCreate = () => {
    setEditing(null);
    goalForm.reset({ name: "", target_amount: "", target_date: "", status: "active", notes: "" });
    setGoalOpen(true);
  };

  const openEdit = (goal: Goal) => {
    setEditing(goal);
    goalForm.reset({
      name: goal.name,
      target_amount: goal.target_amount,
      target_date: goal.target_date ?? "",
      status: goal.status,
      notes: goal.notes ?? "",
    });
    setGoalOpen(true);
  };

  const openContribution = (goal: Goal) => {
    setContributionFor(goal);
    contributionForm.reset({
      amount: "",
      contribution_date: todayISO(),
      note: "",
    });
  };

  const submitGoal = goalForm.handleSubmit(async (values) => {
    const payload = {
      name: values.name,
      target_amount: values.target_amount,
      target_date: values.target_date || null,
      status: values.status,
      notes: values.notes || null,
    };
    try {
      if (editing) {
        await api(`/goals/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) });
        toast.success("Goal updated");
      } else {
        await api("/goals", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Goal created");
      }
      setGoalOpen(false);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  });

  const submitContribution = contributionForm.handleSubmit(async (values) => {
    if (!contributionFor) return;
    try {
      await api(`/goals/${contributionFor.id}/contributions`, {
        method: "POST",
        body: JSON.stringify({
          amount: values.amount,
          contribution_date: values.contribution_date,
          note: values.note || null,
        }),
      });
      toast.success("Contribution added", { description: contributionFor.name });
      setContributionFor(null);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  });

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await api(`/goals/${deleteTarget.id}`, { method: "DELETE" });
    toast.success("Goal deleted");
    refresh();
  };

  const confirmDeleteContribution = async () => {
    if (!deleteContribution) return;
    await api(`/goals/${deleteContribution.goal.id}/contributions/${deleteContribution.id}`, {
      method: "DELETE",
    });
    toast.success("Contribution removed");
    refresh();
  };

  const goals = data ?? [];
  const totalTarget = goals.reduce((sum, goal) => sum + toNumber(goal.target_amount), 0);
  const totalSaved = goals.reduce((sum, goal) => sum + toNumber(goal.current_amount), 0);
  const activeCount = goals.filter((goal) => goal.status === "active").length;
  const completedCount = goals.filter((goal) => goal.status === "completed").length;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Planning"
        title="Goals"
        description="Track what you are saving towards. Contributions are planning records and do not move account balances."
        actions={
          <Button onClick={openCreate}>
            <Plus className="size-4" /> New goal
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total targets" value={formatMoney(totalTarget, { decimals: false })} icon={Target} hint={`${goals.length} goals`} />
        <StatCard label="Contributed" value={formatMoney(totalSaved)} icon={CircleDollarSign} tone="positive" hint={totalTarget ? `${((totalSaved / totalTarget) * 100).toFixed(0)}% of targets` : "No targets yet"} />
        <StatCard label="Active" value={String(activeCount)} icon={Flag} tone="gold" hint="Currently in progress" />
        <StatCard label="Completed" value={String(completedCount)} icon={Trophy} tone="positive" hint="Reached the target" />
      </div>

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {loading ? (
        <LoadingBlock rows={4} />
      ) : goals.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {goals.map((goal) => {
            const progress = Math.min(goal.progress_pct, 100);
            const complete = goal.progress_pct >= 100;
            return (
              <div key={goal.id} className="surface flex flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-semibold">{goal.name}</h3>
                      <Pill className={STATUS_STYLES[goal.status]}>{GOAL_STATUS_LABELS[goal.status]}</Pill>
                    </div>
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {goal.target_date ? `Target ${formatDate(goal.target_date)}` : "No target date"}
                      {goal.contributions.length ? ` · ${goal.contributions.length} contributions` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button size="icon-sm" variant="ghost" title="Edit goal" onClick={() => openEdit(goal)}>
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Delete goal"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(goal)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 flex items-baseline justify-between">
                  <span className="money text-xl font-semibold">{formatMoney(goal.current_amount ?? 0)}</span>
                  <span className="money text-xs text-muted-foreground">of {formatMoney(goal.target_amount, { decimals: false })}</span>
                </div>
                <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all", complete ? "bg-emerald-500" : "bg-primary")}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-[11px]">
                  <span className={cn("font-medium", complete ? "text-emerald-700 dark:text-emerald-400" : "text-primary")}>
                    {percent(goal.progress_pct)} funded
                  </span>
                  <span className="money text-muted-foreground">
                    {toNumber(goal.remaining_amount) > 0
                      ? `${formatMoney(goal.remaining_amount, { decimals: false })} to go`
                      : "Target reached"}
                  </span>
                </div>

                {goal.contributions.length ? (
                  <ul className="mt-3 space-y-1.5 border-t border-border/60 pt-2.5">
                    {goal.contributions.slice(0, 3).map((contribution) => (
                      <li key={contribution.id} className="group flex items-center gap-2 text-[11px]">
                        <span className="text-muted-foreground">{formatDate(contribution.contribution_date, "d MMM")}</span>
                        <span className="min-w-0 flex-1 truncate text-muted-foreground">{contribution.note || "Contribution"}</span>
                        <span className="money font-medium">{formatMoney(contribution.amount, { decimals: false })}</span>
                        <button
                          type="button"
                          title="Remove contribution"
                          onClick={() => setDeleteContribution({ goal, id: contribution.id })}
                          className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}

                <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => openContribution(goal)}>
                  <Plus className="size-3.5" /> Add contribution
                </Button>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Trophy}
          title="No goals yet"
          description="Create a target for an emergency fund, a laptop or a trip, then log contributions as you save."
          action={
            <Button size="sm" onClick={openCreate}>
              <Plus className="size-3.5" /> Create first goal
            </Button>
          }
        />
      )}

      <DefinitionNote>
        Goal progress is the sum of contributions divided by the target. Contributions are planning
        records only; transfer money into savings separately to move the actual balance.
      </DefinitionNote>

      <Dialog open={goalOpen} onOpenChange={setGoalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit goal" : "New goal"}</DialogTitle>
            <DialogDescription>Set a target and track contributions over time.</DialogDescription>
          </DialogHeader>
          <form onSubmit={submitGoal} className="space-y-3">
            <Field label="Name" required htmlFor="goal-name" error={goalForm.formState.errors.name?.message}>
              <Input id="goal-name" placeholder="e.g. Emergency fund" {...goalForm.register("name")} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Target (PKR)" required htmlFor="goal-target" error={goalForm.formState.errors.target_amount?.message}>
                <Input id="goal-target" type="number" step="0.01" min="0" {...goalForm.register("target_amount")} />
              </Field>
              <Field label="Target date" htmlFor="goal-date">
                <Input id="goal-date" type="date" {...goalForm.register("target_date")} />
              </Field>
            </div>
            <Field label="Status" htmlFor="goal-status">
              <NativeSelect
                id="goal-status"
                value={goalForm.watch("status")}
                onChange={(value) => goalForm.setValue("status", value as GoalStatus)}
                options={Object.entries(GOAL_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              />
            </Field>
            <Field label="Notes" htmlFor="goal-notes">
              <Textarea id="goal-notes" rows={2} {...goalForm.register("notes")} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setGoalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={goalForm.formState.isSubmitting}>
                {goalForm.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create goal"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(contributionFor)} onOpenChange={(open) => !open && setContributionFor(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add contribution</DialogTitle>
            <DialogDescription>
              {contributionFor ? `${contributionFor.name} · ${formatMoney(contributionFor.current_amount ?? 0)} saved so far` : ""}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitContribution} className="space-y-3">
            <Field label="Amount (PKR)" required htmlFor="contribution-amount" error={contributionForm.formState.errors.amount?.message}>
              <Input id="contribution-amount" type="number" step="0.01" min="0" {...contributionForm.register("amount")} />
            </Field>
            <Field label="Date" required htmlFor="contribution-date">
              <Input id="contribution-date" type="date" {...contributionForm.register("contribution_date")} />
            </Field>
            <Field label="Note" htmlFor="contribution-note">
              <Input id="contribution-note" placeholder="Optional" {...contributionForm.register("note")} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setContributionFor(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={contributionForm.formState.isSubmitting}>
                {contributionForm.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                Add contribution
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this goal?"
        description="The goal and its contribution history will be removed. Account balances are not affected."
        confirmLabel="Delete goal"
        destructive
        onConfirm={confirmDelete}
      />
      <ConfirmDialog
        open={Boolean(deleteContribution)}
        onOpenChange={(open) => !open && setDeleteContribution(null)}
        title="Remove this contribution?"
        description="Progress will be recalculated. This does not change any account balance."
        confirmLabel="Remove contribution"
        destructive
        onConfirm={confirmDeleteContribution}
      />
    </div>
  );
}
