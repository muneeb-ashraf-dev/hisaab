"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  CalendarClock,
  ArrowLeftRight,
  Landmark,
  PiggyBank,
  Plus,
  ReceiptText,
  Repeat2,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";

import { CashflowChart, CategoryDonut } from "@/components/charts";
import { DateRangePicker } from "@/components/date-range-picker";
import { TransactionFormDialog } from "@/components/transaction-form-dialog";
import { Button } from "@/components/ui/button";
import {
  DefinitionNote,
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  SectionHeading,
  StatCard,
} from "@/components/ui-extras";
import { formatDate, formatMoney, percent, toNumber } from "@/lib/format";
import { useApi, useTrackingPeriod } from "@/lib/hooks";
import type { DashboardOverview } from "@/lib/types";
import { cn } from "@/lib/utils";

function accountIcon(type: string) {
  if (type === "savings") return PiggyBank;
  if (type === "cash") return Banknote;
  return Landmark;
}

function DirectionIcon({ direction, kind }: { direction: "in" | "out"; kind: string }) {
  if (kind === "transfer") return <Repeat2 className="size-3.5" />;
  return direction === "in" ? (
    <ArrowDownLeft className="size-3.5" />
  ) : (
    <ArrowUpRight className="size-3.5" />
  );
}

export default function DashboardPage() {
  const { range, setRange, anchor } = useTrackingPeriod();
  const [newTxnOpen, setNewTxnOpen] = useState(false);
  const query = range ? `/dashboard?start_date=${range.start}&end_date=${range.end}` : null;
  const { data, loading, error, refresh } = useApi<DashboardOverview>(query);

  const savingsRate = useMemo(() => {
    if (!data) return null;
    const income = toNumber(data.period_income);
    if (income <= 0) return null;
    return ((income - toNumber(data.period_expenses_net)) / income) * 100;
  }, [data]);

  const periodTone = data && toNumber(data.period_net_cash_flow) >= 0 ? "positive" : "negative";
  const totalExpense = data?.expense_categories.reduce((sum, item) => sum + toNumber(item.amount), 0) ?? 0;
  const maxAccount = Math.max(...(data?.account_balances.map((item) => toNumber(item.balance)) ?? [0]), 1);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Your money, at a glance"
        description="Every account, transfer and refund in one ledger. Balances are live; reports never mix internal transfers with income or spending."
        actions={
          <>
            {range ? (
              <DateRangePicker value={range} onChange={setRange} anchor={anchor} compact />
            ) : null}
            <Button onClick={() => setNewTxnOpen(true)}>
              <Plus className="size-4" /> New transaction
            </Button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}
      {loading || !range || !data ? (
        <div className="grid gap-4 lg:grid-cols-12">
          <div className="surface p-5 lg:col-span-5">
            <LoadingBlock rows={5} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:col-span-7">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="surface p-5">
                <LoadingBlock rows={2} />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          <section className="grid gap-4 lg:grid-cols-12">
            <div className="surface relative overflow-hidden bg-sidebar p-5 text-sidebar-foreground lg:col-span-5">
              <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-sidebar-primary/10 blur-2xl" />
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-sidebar-foreground/55">
                  Total balance
                </p>
                <span className="rounded-full border border-sidebar-border/80 bg-sidebar-accent/40 px-2 py-0.5 text-[10px] text-sidebar-foreground/60">
                  {formatDate(data.as_of, "d MMM yyyy")}
                </span>
              </div>
              <p className="money mt-4 text-[34px] font-semibold leading-none tracking-tight sm:text-[40px]">
                {formatMoney(data.total_balance)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-sidebar-foreground/55">
                <span>
                  Baseline {formatMoney(data.total_opening_balance, { decimals: false })}
                </span>
                <span className="size-1 rounded-full bg-sidebar-foreground/30" />
                <span>{data.accounts.length} accounts</span>
                <span className="size-1 rounded-full bg-sidebar-foreground/30" />
                <span>Projected {formatMoney(data.projected_balance, { decimals: false })}</span>
              </div>

              <div className="mt-6 space-y-2.5">
                {data.accounts.map((account) => {
                  const Icon = accountIcon(account.account_type);
                  return (
                    <div key={account.id} className="flex items-center gap-2.5">
                      <span className="flex size-7 items-center justify-center rounded-lg bg-sidebar-accent/60 text-sidebar-foreground/70">
                        <Icon className="size-3.5" />
                      </span>
                      <span className="min-w-0 flex-1 truncate text-xs text-sidebar-foreground/75">
                        {account.name}
                      </span>
                      <span className="money text-xs font-medium">
                        {formatMoney(account.current_balance, { decimals: false })}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-5 flex items-center gap-2 border-t border-sidebar-border/60 pt-3 text-[11px] text-sidebar-foreground/55">
                <Sparkles className="size-3.5 text-sidebar-primary" />
                Savings account holds {formatMoney(data.savings_balance, { decimals: false })} of the total.
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-7">
              <StatCard
                label={`Income · ${formatDate(range.start, "MMM d")} – ${formatDate(range.end, "MMM d")}`}
                value={formatMoney(data.period_income)}
                icon={ArrowDownLeft}
                tone="positive"
                hint={`${data.recent_transactions.length ? "Recorded in selected period" : "No income in this period"}`}
              />
              <StatCard
                label="Net spending"
                value={formatMoney(data.period_expenses_net)}
                icon={ReceiptText}
                tone="negative"
                hint={`${formatMoney(data.period_expenses_gross)} gross · ${formatMoney(data.period_refunds)} refunded`}
              />
              <StatCard
                label="Net cash flow"
                value={formatMoney(data.period_net_cash_flow)}
                icon={TrendingUp}
                tone={periodTone}
                hint="Income minus net expenses"
              />
              <StatCard
                label="Savings rate"
                value={savingsRate === null ? "—" : percent(savingsRate)}
                icon={Target}
                tone="gold"
                hint={
                  data.budget
                    ? `Budget used ${data.budget.utilization_pct.toFixed(0)}%`
                    : "Set a budget to track adherence"
                }
              />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-12">
            <div className="surface p-5 lg:col-span-8">
              <SectionHeading
                title="Cash flow"
                description={`Daily movement for ${formatDate(range.start, "d MMM")} – ${formatDate(range.end, "d MMM yyyy")}`}
                action={
                  <div className="hidden items-center gap-3 text-[11px] text-muted-foreground sm:flex">
                    <span className="flex items-center gap-1.5">
                      <span className="size-2 rounded-sm bg-[#2F6B57]" /> Income
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="size-2 rounded-sm bg-[#C05C4B]" /> Net spend
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-0.5 w-3 bg-[#4A7FA5]" /> Net flow
                    </span>
                  </div>
                }
                className="mb-4"
              />
              {data.cashflow.length ? (
                <CashflowChart data={data.cashflow} />
              ) : (
                <EmptyState
                  icon={ArrowLeftRight}
                  title="Nothing recorded in this period"
                  description="Choose another date range or add your first transaction."
                  action={
                    <Button size="sm" variant="outline" onClick={() => setNewTxnOpen(true)}>
                      <Plus className="size-3.5" /> Add transaction
                    </Button>
                  }
                />
              )}
            </div>

            <div className="surface p-5 lg:col-span-4">
              <SectionHeading
                title="Where it went"
                description="Net spending by category"
                className="mb-3"
              />
              {data.expense_categories.length ? (
                <>
                  <div className="relative">
                    <CategoryDonut data={data.expense_categories} />
                    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-1">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                        Total
                      </span>
                      <span className="money text-sm font-semibold">
                        {formatMoney(totalExpense, { decimals: false })}
                      </span>
                    </div>
                  </div>
                  <ul className="mt-2 space-y-2">
                    {data.expense_categories.slice(0, 4).map((slice) => (
                      <li key={slice.category_id ?? slice.name} className="flex items-center gap-2 text-xs">
                        <span
                          className="size-2 shrink-0 rounded-full"
                          style={{ background: slice.color }}
                        />
                        <span className="min-w-0 flex-1 truncate text-muted-foreground">{slice.name}</span>
                        <span className="money font-medium">{formatMoney(slice.amount, { decimals: false })}</span>
                        <span className="w-9 text-right text-[10px] text-muted-foreground">
                          {slice.percentage.toFixed(0)}%
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <EmptyState icon={ReceiptText} title="No spending yet" description="Expenses in this period will be broken down here." />
              )}
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-12">
            <div className="surface p-5 lg:col-span-4">
              <SectionHeading title="Accounts" description="Live balance by account" className="mb-4" />
              <div className="space-y-4">
                {data.account_balances.map((account) => {
                  const meta = data.accounts.find((item) => item.id === account.account_id);
                  const Icon = accountIcon(meta?.account_type ?? "checking");
                  const width = Math.max((toNumber(account.balance) / maxAccount) * 100, 3);
                  return (
                    <div key={account.account_id}>
                      <div className="mb-1.5 flex items-center gap-2">
                        <span className="flex size-6 items-center justify-center rounded-md bg-secondary text-muted-foreground">
                          <Icon className="size-3.5" />
                        </span>
                        <span className="flex-1 text-xs font-medium">{account.name}</span>
                        <span className="money text-xs font-semibold">
                          {formatMoney(account.balance)}
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary/80"
                          style={{ width: `${width}%` }}
                        />
                      </div>
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        Baseline {formatMoney(account.opening_balance, { decimals: false })}
                      </p>
                    </div>
                  );
                })}
              </div>
              <DefinitionNote>
                Balance includes income, expenses, refunds, adjustments and transfers across all dates.
              </DefinitionNote>
            </div>

            <div className="surface p-5 lg:col-span-8">
              <SectionHeading
                title="Recent activity"
                description="Latest entries across every account"
                action={
                  <Link
                    href="/transactions"
                    className="text-xs font-medium text-primary underline-offset-4 hover:underline"
                  >
                    View all
                  </Link>
                }
                className="mb-3"
              />
              {data.recent_transactions.length ? (
                <ul className="divide-y divide-border/70">
                  {data.recent_transactions.slice(0, 6).map((entry) => (
                    <li key={`${entry.entry_kind}-${entry.id}`} className="flex items-center gap-3 py-2.5">
                      <span
                        className={cn(
                          "flex size-8 shrink-0 items-center justify-center rounded-lg",
                          entry.direction === "in"
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                            : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                        )}
                      >
                        <DirectionIcon direction={entry.direction} kind={entry.entry_kind} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-foreground">{entry.description}</p>
                        <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                          {formatDate(entry.entry_date)} ·{" "}
                          {entry.entry_kind === "transfer"
                            ? `${entry.from_account_name ?? "—"} → ${entry.to_account_name ?? "—"}`
                            : entry.category_name ?? entry.account_name ?? "Uncategorized"}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "money shrink-0 text-xs font-semibold",
                          entry.direction === "in" ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"
                        )}
                      >
                        {entry.direction === "in" ? "+" : "−"}
                        {formatMoney(entry.amount, { currency: false })}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon={ReceiptText} title="The ledger is empty" description="Add an income or expense to get started." />
              )}
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-12">
            <div className="surface p-5 lg:col-span-7">
              <SectionHeading
                title="Budget pulse"
                description="Current calendar month"
                action={
                  <Link href="/budgets" className="text-xs font-medium text-primary underline-offset-4 hover:underline">
                    Manage
                  </Link>
                }
                className="mb-4"
              />
              {data.budget || data.budget_progress.length ? (
                <div className="space-y-3">
                  {data.budget_progress.length ? (
                    data.budget_progress.slice(0, 4).map((budget) => (
                      <div key={budget.budget_id ?? budget.category_name ?? "overall"}>
                        <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                          <span className="font-medium">{budget.category_name ?? "Overall budget"}</span>
                          <span className="money text-muted-foreground">
                            {formatMoney(budget.spent, { decimals: false })} / {formatMoney(budget.amount, { decimals: false })}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              budget.utilization_pct >= 100
                                ? "bg-rose-500"
                                : budget.utilization_pct >= budget.warning_threshold
                                  ? "bg-amber-500"
                                  : "bg-primary"
                            )}
                            style={{ width: `${Math.min(budget.utilization_pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <div>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="font-medium">Overall budget</span>
                        <span className="money text-muted-foreground">
                          {formatMoney(data.budget?.spent ?? 0, { decimals: false })} /{" "}
                          {formatMoney(data.budget?.amount ?? 0, { decimals: false })}
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${Math.min(data.budget?.utilization_pct ?? 0, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyState
                  icon={Target}
                  title="No budget for this month"
                  description="Set an overall or category budget to see pace and remaining headroom."
                  action={
                    <Button size="sm" variant="outline" nativeButton={false} render={<Link href="/budgets" />}>
                      Create budget
                    </Button>
                  }
                />
              )}
            </div>

            <div className="surface p-5 lg:col-span-5">
              <SectionHeading
                title="Upcoming"
                description="Recurring payments in the next 30 days"
                action={
                  <Link href="/recurring" className="text-xs font-medium text-primary underline-offset-4 hover:underline">
                    View
                  </Link>
                }
                className="mb-3"
              />
              {data.upcoming_recurring.length ? (
                <ul className="divide-y divide-border/70">
                  {data.upcoming_recurring.slice(0, 4).map((item) => (
                    <li key={`${item.template_id}-${item.due_date}`} className="flex items-center gap-3 py-2.5">
                      <span className="flex size-8 items-center justify-center rounded-lg bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                        <CalendarClock className="size-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium">{item.name}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {formatDate(item.due_date)} · {item.account_name}
                          {item.is_overdue ? " · overdue" : ""}
                        </p>
                      </div>
                      <span className="money text-xs font-semibold">{formatMoney(item.amount, { decimals: false })}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon={CalendarClock} title="Nothing scheduled" description="Recurring templates and reminders will appear here." />
              )}
            </div>
          </section>

          <DefinitionNote>
            <strong className="font-medium text-foreground">How to read this page:</strong> net
            spending is gross expenses minus linked refunds. Transfers and adjustments change account
            balances but are excluded from income and expense totals. Historical usage before the
            baseline is never counted as current spending.
          </DefinitionNote>
        </>
      )}

      <TransactionFormDialog
        open={newTxnOpen}
        onOpenChange={setNewTxnOpen}
        onSaved={refresh}
        defaultAccountId={data?.accounts[0]?.id}
      />
    </div>
  );
}
