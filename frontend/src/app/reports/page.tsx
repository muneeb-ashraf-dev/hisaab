"use client";

import { useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  BarChart3,
  CircleDollarSign,
  Landmark,
  Percent,
  ReceiptText,
  Scale,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { CategoryBars, MonthlySeriesChart, TrendAreaChart } from "@/components/charts";
import { DateRangePicker } from "@/components/date-range-picker";
import { Field, NativeSelect } from "@/components/select-field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DefinitionNote,
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Pill,
  SectionHeading,
  StatCard,
} from "@/components/ui-extras";
import { formatDate, formatMoney, percent, toNumber } from "@/lib/format";
import {
  currentYearAnchor,
  useApi,
  useReferenceData,
  useTrackingPeriod,
} from "@/lib/hooks";
import type {
  AccountReport,
  AnalyticsReport,
  AnnualReport,
  CategoryReport,
  CategorySpend,
  MonthlyReport,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type TabValue = "monthly" | "annual" | "categories" | "accounts" | "analytics";

function ChangePill({ value, invert = false }: { value: number | null | undefined; invert?: boolean }) {
  if (value === null || value === undefined) {
    return <span className="text-[10px] text-muted-foreground">no prior data</span>;
  }
  const positive = value >= 0;
  const good = invert ? !positive : positive;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
        good
          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
      )}
    >
      {positive ? <TrendingUp className="size-2.5" /> : <TrendingDown className="size-2.5" />}
      {value >= 0 ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  );
}

function CategoryTable({
  categories,
  showPrevious = false,
}: {
  categories: CategorySpend[];
  showPrevious?: boolean;
}) {
  if (!categories.length) {
    return <EmptyState icon={ReceiptText} title="No category activity" description="Expenses in this period will be categorised here." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border/70 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            <th className="px-3 py-2 font-medium">Category</th>
            <th className="px-3 py-2 text-right font-medium">Net spend</th>
            <th className="px-3 py-2 text-right font-medium">Share</th>
            <th className="px-3 py-2 text-right font-medium">Txns</th>
            <th className="px-3 py-2 text-right font-medium">Avg</th>
            {showPrevious ? <th className="px-3 py-2 text-right font-medium">Previous</th> : null}
            {showPrevious ? <th className="px-3 py-2 text-right font-medium">Change</th> : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {categories.map((category) => (
            <tr key={category.category_id ?? category.name} className="hover:bg-muted/20">
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full" style={{ background: category.color }} />
                  <span className="text-[13px] font-medium">{category.name}</span>
                  {category.is_essential ? (
                    <Pill className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
                      essential
                    </Pill>
                  ) : null}
                  {category.expense_nature ? (
                    <span className="text-[10px] text-muted-foreground">{category.expense_nature}</span>
                  ) : null}
                </div>
              </td>
              <td className="money px-3 py-2.5 text-right text-[13px] font-semibold">{formatMoney(category.amount)}</td>
              <td className="px-3 py-2.5 text-right text-xs text-muted-foreground">{category.percentage.toFixed(1)}%</td>
              <td className="px-3 py-2.5 text-right text-xs text-muted-foreground">{category.transaction_count}</td>
              <td className="money px-3 py-2.5 text-right text-xs text-muted-foreground">{formatMoney(category.average_amount, { decimals: false })}</td>
              {showPrevious ? (
                <td className="money px-3 py-2.5 text-right text-xs text-muted-foreground">
                  {formatMoney(category.previous_amount ?? 0, { decimals: false })}
                </td>
              ) : null}
              {showPrevious ? (
                <td className="px-3 py-2.5 text-right">
                  <ChangePill value={category.change_pct} invert />
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReconciliationStrip({
  opening,
  baseline,
  netCashFlow,
  adjustments,
  closing,
  difference,
}: {
  opening: string;
  baseline: string;
  netCashFlow: string;
  adjustments: string;
  closing: string;
  difference?: string;
}) {
  const parts = [
    { label: "Opening", value: formatMoney(opening) },
    { label: "Baseline", value: formatMoney(baseline) },
    { label: "Net cash flow", value: formatMoney(netCashFlow) },
    { label: "Adjustments", value: formatMoney(adjustments) },
    { label: "Closing", value: formatMoney(closing) },
  ];
  return (
    <div className="surface p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2">
          <Scale className="size-4 text-muted-foreground" />
          <div>
            <p className="text-xs font-medium">Reconciliation</p>
            <p className="text-[10px] text-muted-foreground">Opening + baseline + net flow + adjustments = closing</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {parts.map((part, index) => (
            <div key={part.label} className="flex items-center gap-4">
              {index > 0 ? <span className="text-border">+</span> : null}
              <div>
                <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">{part.label}</p>
                <p className="money text-xs font-semibold">{part.value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
      {difference ? (
        <p
          className={cn(
            "mt-2 rounded-md px-2 py-1 text-[10px]",
            toNumber(difference) === 0
              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
              : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
          )}
        >
          Reconciliation difference: {formatMoney(difference)} {toNumber(difference) === 0 ? "· balanced" : "· investigate"}
        </p>
      ) : null}
    </div>
  );
}

export default function ReportsPage() {
  const { range, setRange, anchor, status } = useTrackingPeriod();
  const { accounts } = useReferenceData();
  const [tab, setTab] = useState<TabValue>("monthly");
  const years = useApi<number[]>("/reports/years");
  const [year, setYear] = useState<number | null>(null);
  const selectedYear =
    year ?? years.data?.[0] ?? currentYearAnchor(status.data?.baseline_date);
  const [accountId, setAccountId] = useState("");
  const selectedAccountId = accountId || accounts[0]?.id || "";

  const monthly = useApi<MonthlyReport>(
    tab === "monthly" && range ? `/reports/monthly?start_date=${range.start}&end_date=${range.end}` : null
  );
  const annual = useApi<AnnualReport>(tab === "annual" ? `/reports/annual?year=${selectedYear}` : null);
  const categories = useApi<CategoryReport>(
    tab === "categories" && range ? `/reports/categories?start_date=${range.start}&end_date=${range.end}` : null
  );
  const account = useApi<AccountReport>(
    tab === "accounts" && range && selectedAccountId
      ? `/reports/accounts/${selectedAccountId}?start_date=${range.start}&end_date=${range.end}`
      : null
  );
  const analytics = useApi<AnalyticsReport>(
    tab === "analytics" && range ? `/reports/analytics?start_date=${range.start}&end_date=${range.end}` : null
  );

  const yearOptions = useMemo(() => {
    const values = new Set<number>(years.data ?? []);
    values.add(selectedYear);
    return Array.from(values)
      .sort((a, b) => b - a)
      .map((value) => ({ value: String(value), label: String(value) }));
  }, [years.data, selectedYear]);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Insights"
        title="Reports"
        description="Monthly and annual reconciliation, category intelligence, per-account statements and behavioural analytics — all computed from the same ledger."
        actions={
          <>
            {tab === "annual" ? (
              <div className="w-28">
                <NativeSelect
                  value={String(selectedYear)}
                  onChange={(value) => setYear(Number(value))}
                  options={yearOptions}
                  aria-label="Report year"
                />
              </div>
            ) : range ? (
              <DateRangePicker value={range} onChange={setRange} anchor={anchor} compact />
            ) : null}
          </>
        }
      />

      <Tabs value={tab} onValueChange={(value) => setTab(value as TabValue)}>
        <TabsList className="h-9 w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="monthly">Monthly</TabsTrigger>
          <TabsTrigger value="annual">Annual</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="monthly" className="mt-4 space-y-4">
          {!range || monthly.loading ? (
            <LoadingBlock rows={6} />
          ) : monthly.error ? (
            <ErrorState message={monthly.error} onRetry={monthly.refresh} />
          ) : monthly.data ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="font-heading text-lg font-semibold">{monthly.data.label}</h2>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(monthly.data.start_date)} – {formatDate(monthly.data.end_date)}
                    {monthly.data.is_partial_month ? " · partial month" : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <Pill className="border-border bg-card">
                    {monthly.data.transaction_count} transactions
                  </Pill>
                  {monthly.data.budget_adherence_pct !== null ? (
                    <Pill className="border-border bg-card">
                      Budget used {percent(monthly.data.budget_adherence_pct, 0)}
                    </Pill>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Income" value={formatMoney(monthly.data.income)} icon={ArrowDownLeft} tone="positive" />
                <StatCard
                  label="Net spending"
                  value={formatMoney(monthly.data.expenses_net)}
                  icon={ReceiptText}
                  tone="negative"
                  hint={`${formatMoney(monthly.data.expenses_gross)} gross − ${formatMoney(monthly.data.refunds)} refunds`}
                />
                <StatCard
                  label="Net cash flow"
                  value={formatMoney(monthly.data.net_cash_flow)}
                  icon={TrendingUp}
                  tone={toNumber(monthly.data.net_cash_flow) >= 0 ? "positive" : "negative"}
                />
                <StatCard
                  label="Savings rate"
                  value={percent(monthly.data.savings_rate_pct)}
                  icon={Percent}
                  tone="gold"
                  hint={
                    monthly.data.comparison.expenses_change_pct !== null
                      ? `Spending ${monthly.data.comparison.expenses_change_pct >= 0 ? "up" : "down"} ${Math.abs(monthly.data.comparison.expenses_change_pct).toFixed(1)}% vs prior`
                      : "No previous period to compare"
                  }
                />
              </div>

              <ReconciliationStrip
                opening={monthly.data.opening_balance}
                baseline={monthly.data.baseline_effect}
                netCashFlow={monthly.data.net_cash_flow}
                adjustments={monthly.data.adjustments_net}
                closing={monthly.data.closing_balance}
                difference={monthly.data.reconciliation_difference}
              />

              <div className="grid gap-4 lg:grid-cols-12">
                <div className="surface p-4 lg:col-span-8">
                  <SectionHeading title="Category breakdown" description="Net of linked refunds" className="mb-3" />
                  <CategoryTable categories={monthly.data.categories} />
                </div>
                <div className="space-y-4 lg:col-span-4">
                  <div className="surface p-4">
                    <SectionHeading title="Accounts" description="Opening → closing" className="mb-3" />
                    <div className="space-y-3">
                      {monthly.data.accounts.map((item) => (
                        <div key={item.account_id} className="rounded-lg border border-border/70 p-2.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium">{item.account_name}</span>
                            <span className="money font-semibold">{formatMoney(item.closing_balance)}</span>
                          </div>
                          <p className="mt-1 text-[10px] text-muted-foreground">
                            Opening {formatMoney(item.opening_balance, { decimals: false })} · in{" "}
                            {formatMoney(item.income, { decimals: false })} · out{" "}
                            {formatMoney(item.expenses_net, { decimals: false })} · transfers{" "}
                            {formatMoney(item.transfers_in, { decimals: false })} /{" "}
                            {formatMoney(item.transfers_out, { decimals: false })}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="surface p-4">
                    <SectionHeading title="Period comparison" className="mb-3" />
                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Income</span>
                        <div className="flex items-center gap-2">
                          <span className="money">{formatMoney(monthly.data.comparison.previous_income ?? 0, { decimals: false })}</span>
                          <ChangePill value={monthly.data.comparison.income_change_pct} />
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Net spending</span>
                        <div className="flex items-center gap-2">
                          <span className="money">{formatMoney(monthly.data.comparison.previous_expenses ?? 0, { decimals: false })}</span>
                          <ChangePill value={monthly.data.comparison.expenses_change_pct} invert />
                        </div>
                      </div>
                      <div className="flex items-center justify-between border-t border-border/60 pt-2">
                        <span className="text-muted-foreground">Net change</span>
                        <span className="money font-semibold">{formatMoney(monthly.data.comparison.net_change ?? 0)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="surface p-4">
                <SectionHeading title="Largest expenses" description="Top outflows in this period" className="mb-3" />
                {monthly.data.largest_expenses.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                          <th className="px-3 py-2 font-medium">Date</th>
                          <th className="px-3 py-2 font-medium">Description</th>
                          <th className="px-3 py-2 font-medium">Category</th>
                          <th className="px-3 py-2 font-medium">Account</th>
                          <th className="px-3 py-2 text-right font-medium">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {monthly.data.largest_expenses.map((item) => (
                          <tr key={item.id}>
                            <td className="px-3 py-2 text-xs text-muted-foreground">{formatDate(item.transaction_date)}</td>
                            <td className="px-3 py-2 text-[13px]">{item.description}</td>
                            <td className="px-3 py-2 text-xs text-muted-foreground">{item.category_name ?? "—"}</td>
                            <td className="px-3 py-2 text-xs text-muted-foreground">{item.account_name ?? "—"}</td>
                            <td className="money px-3 py-2 text-right text-[13px] font-semibold">{formatMoney(item.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState icon={ReceiptText} title="No expenses" description="There are no expenses recorded in this period." />
                )}
              </div>
            </>
          ) : null}
        </TabsContent>

        <TabsContent value="annual" className="mt-4 space-y-4">
          {annual.loading ? (
            <LoadingBlock rows={6} />
          ) : annual.error ? (
            <ErrorState message={annual.error} onRetry={annual.refresh} />
          ) : annual.data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Income" value={formatMoney(annual.data.income)} icon={ArrowDownLeft} tone="positive" />
                <StatCard
                  label="Net expenses"
                  value={formatMoney(annual.data.expenses_net)}
                  icon={ReceiptText}
                  tone="negative"
                  hint={`Monthly avg ${formatMoney(annual.data.monthly_average_expenses, { decimals: false })}`}
                />
                <StatCard label="Net cash flow" value={formatMoney(annual.data.net_cash_flow)} icon={TrendingUp} tone={toNumber(annual.data.net_cash_flow) >= 0 ? "positive" : "negative"} />
                <StatCard label="Savings rate" value={percent(annual.data.savings_rate_pct)} icon={Percent} tone="gold" hint={`${annual.data.transaction_count} transactions`} />
              </div>

              <div className="surface p-4">
                <SectionHeading
                  title={`${annual.data.year} monthly rhythm`}
                  description="Income, net expenses and closing balance"
                  className="mb-3"
                />
                <MonthlySeriesChart data={annual.data.months} />
              </div>

              <div className="grid gap-4 lg:grid-cols-12">
                <div className="surface p-4 lg:col-span-7">
                  <SectionHeading title="Month-by-month" className="mb-3" />
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[500px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                          <th className="px-3 py-2 font-medium">Month</th>
                          <th className="px-3 py-2 text-right font-medium">Income</th>
                          <th className="px-3 py-2 text-right font-medium">Net expenses</th>
                          <th className="px-3 py-2 text-right font-medium">Net flow</th>
                          <th className="px-3 py-2 text-right font-medium">Closing</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {annual.data.months.map((point) => (
                          <tr key={point.month}>
                            <td className="px-3 py-2 text-xs font-medium">{point.label}</td>
                            <td className="money px-3 py-2 text-right text-xs">{formatMoney(point.income, { decimals: false })}</td>
                            <td className="money px-3 py-2 text-right text-xs">{formatMoney(point.net_expenses, { decimals: false })}</td>
                            <td className={cn("money px-3 py-2 text-right text-xs", toNumber(point.net_cash_flow) >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400")}>
                              {formatMoney(point.net_cash_flow, { decimals: false })}
                            </td>
                            <td className="money px-3 py-2 text-right text-xs font-medium">{formatMoney(point.closing_balance, { decimals: false })}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="space-y-4 lg:col-span-5">
                  <div className="surface p-4">
                    <SectionHeading title="Highlights" className="mb-3" />
                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Highest spending month</span>
                        <span className="font-medium">
                          {annual.data.highest_spending_month
                            ? `${annual.data.highest_spending_month.label} · ${formatMoney(annual.data.highest_spending_month.net_expenses, { decimals: false })}`
                            : "—"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Top category</span>
                        <span className="font-medium">
                          {annual.data.highest_spending_category
                            ? `${annual.data.highest_spending_category.name} · ${formatMoney(annual.data.highest_spending_category.amount, { decimals: false })}`
                            : "—"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between border-t border-border/60 pt-2">
                        <span className="text-muted-foreground">Closing balance</span>
                        <span className="money font-semibold">{formatMoney(annual.data.closing_balance)}</span>
                      </div>
                      {annual.data.year_over_year ? (
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">vs {String(annual.data.year_over_year.year ?? "prior year")}</span>
                          <ChangePill value={annual.data.year_over_year.expenses_change_pct as number | null} invert />
                        </div>
                      ) : null}
                    </div>
                  </div>
                  <div className="surface p-4">
                    <SectionHeading title="Account movement" className="mb-3" />
                    <div className="space-y-2">
                      {annual.data.accounts.map((item) => (
                        <div key={item.account_id} className="flex items-center justify-between rounded-lg border border-border/70 px-2.5 py-2 text-xs">
                          <span className="font-medium">{item.account_name}</span>
                          <span className="money">{formatMoney(item.closing_balance, { decimals: false })}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="surface p-4">
                <SectionHeading title="Category totals" description={`${annual.data.year} net of refunds`} className="mb-3" />
                <CategoryTable categories={annual.data.categories} />
              </div>
            </>
          ) : null}
        </TabsContent>

        <TabsContent value="categories" className="mt-4 space-y-4">
          {!range || categories.loading ? (
            <LoadingBlock rows={6} />
          ) : categories.error ? (
            <ErrorState message={categories.error} onRetry={categories.refresh} />
          ) : categories.data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <StatCard
                  label="Net expenses"
                  value={formatMoney(categories.data.total_expenses_net)}
                  icon={ReceiptText}
                  tone="negative"
                  hint={`${formatDate(categories.data.start_date)} – ${formatDate(categories.data.end_date)}`}
                />
                <StatCard
                  label="Previous period"
                  value={formatMoney(categories.data.previous_total_expenses_net)}
                  icon={ReceiptText}
                  hint={`${formatDate(categories.data.previous_start, "d MMM")} – ${formatDate(categories.data.previous_end, "d MMM")}`}
                />
                <StatCard
                  label="Change"
                  value={percent(categories.data.total_change_pct)}
                  icon={TrendingUp}
                  tone={toNumber(categories.data.total_change_pct) <= 0 ? "positive" : "negative"}
                  hint="Lower spending is better"
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-12">
                <div className="surface p-4 lg:col-span-5">
                  <SectionHeading title="Share of spending" className="mb-2" />
                  <CategoryBars data={categories.data.categories.slice(0, 8)} />
                </div>
                <div className="surface p-4 lg:col-span-7">
                  <SectionHeading title="Category detail" description="Compared with the immediately preceding period" className="mb-3" />
                  <CategoryTable categories={categories.data.categories} showPrevious />
                </div>
              </div>

              <div className="surface p-4">
                <SectionHeading title="Monthly trend" description="Net expenses by month" className="mb-3" />
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border/70 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                        <th className="px-3 py-2 font-medium">Month</th>
                        <th className="px-3 py-2 text-right font-medium">Net expenses</th>
                        <th className="px-3 py-2 font-medium">Composition</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {categories.data.monthly_trend.map((point) => {
                        const entries = Object.entries(point.categories)
                          .map(([id, amount]) => ({
                            name: categories.data?.categories.find((c) => c.category_id === id)?.name ?? "Category",
                            amount: toNumber(amount),
                          }))
                          .sort((a, b) => b.amount - a.amount)
                          .slice(0, 3);
                        return (
                          <tr key={point.month}>
                            <td className="px-3 py-2 text-xs font-medium">{point.label}</td>
                            <td className="money px-3 py-2 text-right text-xs font-semibold">{formatMoney(point.total, { decimals: false })}</td>
                            <td className="px-3 py-2 text-[10px] text-muted-foreground">
                              {entries.length
                                ? entries.map((entry) => `${entry.name} ${formatMoney(entry.amount, { decimals: false, currency: false })}`).join(" · ")
                                : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <DefinitionNote>
                Category amounts are net: refunds reduce the category of the original expense.
                Percentages use absolute net spending. Previous period is the same length immediately
                before the selected range.
              </DefinitionNote>
            </>
          ) : null}
        </TabsContent>

        <TabsContent value="accounts" className="mt-4 space-y-4">
          <div className="surface flex flex-wrap items-end gap-3 p-3">
            <Field label="Account" className="w-full sm:w-64">
              <NativeSelect
                value={selectedAccountId}
                onChange={setAccountId}
                options={accounts.map((item) => ({ value: item.id, label: item.name }))}
                placeholder="Choose account"
              />
            </Field>
            <p className="pb-2 text-[11px] text-muted-foreground">
              Full statement, category split and income sources for one account.
            </p>
          </div>

          {account.loading ? (
            <LoadingBlock rows={6} />
          ) : account.error ? (
            <ErrorState message={account.error} onRetry={account.refresh} />
          ) : account.data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Current balance" value={formatMoney(account.data.current_balance)} icon={Landmark} hint={`${account.data.account_type} · ${account.data.currency}`} />
                <StatCard label="Period inflow" value={formatMoney(toNumber(account.data.income) + toNumber(account.data.transfers_in) + toNumber(account.data.refunds) + toNumber(account.data.adjustments_increase))} icon={ArrowDownLeft} tone="positive" hint={`${formatMoney(account.data.income)} income`} />
                <StatCard label="Period outflow" value={formatMoney(toNumber(account.data.expenses_gross) + toNumber(account.data.transfers_out) + toNumber(account.data.adjustments_decrease))} icon={ArrowUpRight} tone="negative" hint={`${formatMoney(account.data.expenses_net)} net spend`} />
                <StatCard label="Closing" value={formatMoney(account.data.closing_balance)} icon={CircleDollarSign} tone="gold" hint={`Opening ${formatMoney(account.data.opening_balance, { decimals: false })}`} />
              </div>

              <div className="grid gap-4 lg:grid-cols-12">
                <div className="surface p-4 lg:col-span-7">
                  <SectionHeading title="Account statement" description={`${formatDate(account.data.start_date)} – ${formatDate(account.data.end_date)}`} className="mb-3" />
                  {account.data.history.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[540px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-border/70 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                            <th className="px-3 py-2 font-medium">Date</th>
                            <th className="px-3 py-2 font-medium">Description</th>
                            <th className="px-3 py-2 font-medium">Category</th>
                            <th className="px-3 py-2 text-right font-medium">Amount</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/60">
                          {account.data.history.map((entry) => (
                            <tr key={`${entry.entry_kind}-${entry.id}`}>
                              <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">{formatDate(entry.entry_date)}</td>
                              <td className="px-3 py-2 text-[13px]">{entry.description}</td>
                              <td className="px-3 py-2 text-xs text-muted-foreground">
                                {entry.entry_kind === "transfer" ? `${entry.from_account_name} → ${entry.to_account_name}` : entry.category_name ?? "—"}
                              </td>
                              <td className={cn("money px-3 py-2 text-right text-xs font-semibold", entry.direction === "in" ? "text-emerald-700 dark:text-emerald-400" : "text-foreground")}>
                                {entry.direction === "in" ? "+" : "−"}
                                {formatMoney(entry.amount, { currency: false })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState icon={ReceiptText} title="No activity" description="This account has no entries in the selected period." />
                  )}
                </div>
                <div className="space-y-4 lg:col-span-5">
                  <div className="surface p-4">
                    <SectionHeading title="Spending by category" className="mb-3" />
                    <CategoryTable categories={account.data.categories} />
                  </div>
                  <div className="surface p-4">
                    <SectionHeading title="Income sources" className="mb-3" />
                    {account.data.income_sources.length ? (
                      <ul className="space-y-2">
                        {account.data.income_sources.map((source) => (
                          <li key={source.name} className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">{source.name}</span>
                            <span className="money font-medium">{formatMoney(source.amount)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground">No income recorded for this account in the period.</p>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <EmptyState icon={Landmark} title="Choose an account" description="Select an account to view its statement." />
          )}
        </TabsContent>

        <TabsContent value="analytics" className="mt-4 space-y-4">
          {!range || analytics.loading ? (
            <LoadingBlock rows={6} />
          ) : analytics.error ? (
            <ErrorState message={analytics.error} onRetry={analytics.refresh} />
          ) : analytics.data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Savings rate" value={percent(analytics.data.savings_rate_pct)} icon={Percent} tone="positive" hint="(income − net spend) / income" />
                <StatCard label="Fixed expenses" value={formatMoney(analytics.data.fixed_expenses)} icon={Scale} tone="default" hint={analytics.data.variable_expenses !== "0.00" ? `Variable ${formatMoney(analytics.data.variable_expenses, { decimals: false })}` : "No split available"} />
                <StatCard label="Essential" value={formatMoney(analytics.data.essential_expenses)} icon={Target} tone="gold" hint={`Discretionary ${formatMoney(analytics.data.discretionary_expenses, { decimals: false })}`} />
                <StatCard label="Top category share" value={percent(analytics.data.top_category_share_pct)} icon={BarChart3} tone="default" hint={analytics.data.category_concentration[0]?.name ?? "No categories"} />
              </div>

              <div className="grid gap-4 lg:grid-cols-12">
                <div className="surface p-4 lg:col-span-7">
                  <SectionHeading title="Spending trend" description="Net expenses by month" className="mb-2" />
                  <TrendAreaChart data={analytics.data.spending_trend} />
                </div>
                <div className="surface p-4 lg:col-span-5">
                  <SectionHeading title="Income sources" className="mb-3" />
                  {analytics.data.income_sources.length ? (
                    <div className="space-y-3">
                      {analytics.data.income_sources.map((source) => (
                        <div key={source.name}>
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium">{source.name}</span>
                            <span className="money">{formatMoney(source.amount)}</span>
                          </div>
                          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                            <div className="h-full rounded-full bg-primary/80" style={{ width: `${Math.min(source.percentage, 100)}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">No income recorded in this period.</p>
                  )}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="surface p-4">
                  <SectionHeading
                    title="Unusually large expenses"
                    description={
                      analytics.data.large_expense_threshold
                        ? `Above ${formatMoney(analytics.data.large_expense_threshold)} (Tukey fence)`
                        : "Requires at least five expenses in the period"
                    }
                    className="mb-3"
                  />
                  {analytics.data.large_expenses.length ? (
                    <ul className="divide-y divide-border/60">
                      {analytics.data.large_expenses.map((item) => (
                        <li key={item.id} className="flex items-center gap-3 py-2.5">
                          <span className="flex size-7 items-center justify-center rounded-lg bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300">
                            <TrendingUp className="size-3.5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-medium">{item.description}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {formatDate(item.transaction_date)} · {item.category_name ?? "Uncategorized"} · {item.multiple_of_median.toFixed(1)}× median
                            </p>
                          </div>
                          <span className="money text-xs font-semibold">{formatMoney(item.amount)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState icon={Sparkles} title="Nothing unusual" description="No expense exceeds the outlier threshold in this period." />
                  )}
                </div>

                <div className="surface p-4">
                  <SectionHeading title="Recurring candidates" description="Seen 3+ times across 2+ months" className="mb-3" />
                  {analytics.data.recurring_candidates.length ? (
                    <ul className="divide-y divide-border/60">
                      {analytics.data.recurring_candidates.map((item) => (
                        <li key={`${item.merchant_or_payee}-${item.last_seen}`} className="flex items-center gap-3 py-2.5">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-medium">{item.merchant_or_payee ?? "Unnamed"}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {item.category_name ?? "Uncategorized"} · {item.transaction_count}× · last {formatDate(item.last_seen)} · spread {item.amount_range_pct.toFixed(0)}%
                            </p>
                          </div>
                          <span className="money text-xs font-semibold">{formatMoney(item.average_amount)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState icon={Sparkles} title="No recurring patterns yet" description="Add more history to detect repeat payments." />
                  )}
                </div>
              </div>

              <div className="surface p-4">
                <SectionHeading title="Concentration" description="Largest categories by net spending" className="mb-3" />
                <CategoryTable categories={analytics.data.category_concentration} />
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(analytics.data.definitions).map(([key, text]) => (
                  <DefinitionNote key={key}>
                    <span className="font-medium capitalize text-foreground">{key.replaceAll("_", " ")}: </span>
                    {text}
                  </DefinitionNote>
                ))}
              </div>
            </>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
