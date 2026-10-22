export type Money = string;

export type AccountType = "checking" | "savings" | "cash" | "other";
export type TransactionType =
  | "income"
  | "expense"
  | "refund"
  | "adjustment_increase"
  | "adjustment_decrease";
export type CategoryType = "income" | "expense";
export type ExpenseNature = "fixed" | "variable" | "mixed";
export type GoalStatus = "active" | "completed" | "paused" | "cancelled";
export type RecurringFrequency = "weekly" | "monthly" | "quarterly" | "yearly";
export type LedgerEntryKind = "transaction" | "transfer";

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface Account {
  id: string;
  name: string;
  account_type: AccountType;
  currency: string;
  opening_balance: Money;
  opening_date: string;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountActivity {
  id: string;
  entry_kind: string;
  entry_date: string;
  description: string;
  amount: Money;
  direction: "in" | "out";
  category_name: string | null;
  counterparty_account: string | null;
}

export interface AccountWithBalance extends Account {
  current_balance: Money;
  projected_balance: Money;
  period_income: Money;
  period_expenses: Money;
  recent_activity: AccountActivity[];
}

export interface Category {
  id: string;
  name: string;
  category_type: CategoryType;
  parent_category_id: string | null;
  parent_name: string | null;
  icon: string;
  color: string;
  is_active: boolean;
  is_essential: boolean;
  expense_nature: ExpenseNature;
  sort_order: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  transaction_count: number;
}

export interface Transaction {
  id: string;
  transaction_date: string;
  transaction_type: TransactionType;
  amount: Money;
  account_id: string;
  account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  category_color: string | null;
  committee_id: string | null;
  committee_name: string | null;
  description: string;
  merchant_or_payee: string | null;
  payment_method: string | null;
  notes: string | null;
  related_transaction_id: string | null;
  source: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  refunded_amount: Money | null;
  net_amount: Money | null;
}

export interface TransactionDetail {
  transaction: Transaction;
  refunds: Transaction[];
  original_transaction: Transaction | null;
  refundable_remaining: Money;
}

export interface Transfer {
  id: string;
  transfer_date: string;
  from_account_id: string;
  to_account_id: string;
  from_account_name: string | null;
  to_account_name: string | null;
  amount: Money;
  description: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LedgerEntry {
  id: string;
  entry_kind: LedgerEntryKind;
  entry_date: string;
  amount: Money;
  direction: "in" | "out";
  transaction_type: TransactionType | null;
  description: string;
  account_id: string | null;
  account_name: string | null;
  from_account_id: string | null;
  from_account_name: string | null;
  to_account_id: string | null;
  to_account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  category_color: string | null;
  committee_id: string | null;
  committee_name: string | null;
  merchant_or_payee: string | null;
  payment_method: string | null;
  notes: string | null;
  related_transaction_id: string | null;
  created_at: string | null;
}

export interface TrendPoint {
  month: string;
  label: string;
  income: Money;
  expenses: Money;
  refunds: Money;
  net_cash_flow: Money;
  net_expenses: Money;
}

export interface CategorySlice {
  category_id: string | null;
  name: string;
  color: string;
  amount: Money;
  percentage: number;
  transaction_count: number;
}

export interface AccountBalancePoint {
  account_id: string;
  name: string;
  balance: Money;
  opening_balance: Money;
}

export interface BudgetProgress {
  budget_id: string | null;
  category_id: string | null;
  category_name: string | null;
  amount: Money;
  spent: Money;
  remaining: Money;
  utilization_pct: number;
  warning_threshold: number;
  status: string;
  notes: string | null;
}

export interface UpcomingRecurring {
  template_id: string;
  name: string;
  description: string;
  amount: Money;
  transaction_type: TransactionType;
  due_date: string;
  account_id: string;
  account_name: string;
  category_name: string | null;
  is_overdue: boolean;
  occurrence_status: string;
}

export interface DashboardOverview {
  as_of: string;
  period_start: string;
  period_end: string;
  total_balance: Money;
  projected_balance: Money;
  total_opening_balance: Money;
  period_income: Money;
  period_expenses_gross: Money;
  period_refunds: Money;
  period_expenses_net: Money;
  period_net_cash_flow: Money;
  savings_balance: Money;
  savings_income_this_month: Money;
  month_start: string;
  month_income: Money;
  month_expenses_gross: Money;
  month_refunds: Money;
  month_expenses: Money;
  month_net_cash_flow: Money;
  budget: BudgetProgress | null;
  budget_progress: BudgetProgress[];
  accounts: AccountWithBalance[];
  cashflow: TrendPoint[];
  expense_categories: CategorySlice[];
  account_balances: AccountBalancePoint[];
  recent_transactions: LedgerEntry[];
  upcoming_recurring: UpcomingRecurring[];
  has_any_transactions: boolean;
  days_remaining_in_month: number;
}

export interface CategorySpend {
  category_id: string | null;
  name: string;
  color: string;
  amount: Money;
  percentage: number;
  transaction_count: number;
  average_amount: Money;
  largest_amount: Money;
  is_essential: boolean | null;
  expense_nature: string | null;
  previous_amount: Money | null;
  change_pct: number | null;
}

export interface AccountPeriodSummary {
  account_id: string;
  account_name: string;
  opening_balance: Money;
  closing_balance: Money;
  income: Money;
  expenses_gross: Money;
  refunds: Money;
  expenses_net: Money;
  transfers_in: Money;
  transfers_out: Money;
  adjustments_increase: Money;
  adjustments_decrease: Money;
  net_movement: Money;
  transaction_count: number;
}

export interface MonthlyPoint {
  month: string;
  label: string;
  income: Money;
  expenses: Money;
  refunds: Money;
  net_expenses: Money;
  adjustments_net: Money;
  net_cash_flow: Money;
  closing_balance: Money;
  opening_balance: Money;
  baseline_effect: Money;
}

export interface PeriodComparison {
  previous_start: string | null;
  previous_end: string | null;
  income_change_pct: number | null;
  expenses_change_pct: number | null;
  net_change: Money | null;
  previous_income: Money | null;
  previous_expenses: Money | null;
}

export interface LargestExpense {
  id: string;
  transaction_date: string;
  description: string;
  amount: Money;
  category_name: string | null;
  account_name: string | null;
  merchant_or_payee: string | null;
}

export interface MonthlyReport {
  start_date: string;
  end_date: string;
  label: string;
  is_partial_month: boolean;
  opening_balance: Money;
  baseline_effect: Money;
  income: Money;
  expenses_gross: Money;
  refunds: Money;
  expenses_net: Money;
  net_cash_flow: Money;
  adjustments_increase: Money;
  adjustments_decrease: Money;
  adjustments_net: Money;
  transfers_in: Money;
  transfers_out: Money;
  closing_balance: Money;
  savings_rate_pct: number | null;
  accounts: AccountPeriodSummary[];
  categories: CategorySpend[];
  largest_expenses: LargestExpense[];
  budgets: BudgetProgress[];
  budget_adherence_pct: number | null;
  comparison: PeriodComparison;
  reconciliation_difference: Money;
  transaction_count: number;
}

export interface AnnualReport {
  year: number;
  start_date: string;
  end_date: string;
  opening_balance: Money;
  baseline_effect: Money;
  income: Money;
  expenses_gross: Money;
  refunds: Money;
  expenses_net: Money;
  net_cash_flow: Money;
  adjustments_net: Money;
  closing_balance: Money;
  savings_rate_pct: number | null;
  months: MonthlyPoint[];
  accounts: AccountPeriodSummary[];
  categories: CategorySpend[];
  monthly_average_expenses: Money;
  highest_spending_month: MonthlyPoint | null;
  highest_spending_category: CategorySpend | null;
  year_over_year: Record<string, unknown> | null;
  transaction_count: number;
}

export interface CategoryReport {
  start_date: string;
  end_date: string;
  total_expenses_net: Money;
  categories: CategorySpend[];
  previous_start: string;
  previous_end: string;
  previous_total_expenses_net: Money;
  total_change_pct: number | null;
  monthly_trend: Array<{
    month: string;
    label: string;
    total: Money;
    categories: Record<string, Money>;
  }>;
  definitions: Record<string, string>;
}

export interface AccountReport {
  account_id: string;
  account_name: string;
  account_type: string;
  currency: string;
  start_date: string;
  end_date: string;
  opening_balance: Money;
  closing_balance: Money;
  current_balance: Money;
  income: Money;
  expenses_gross: Money;
  refunds: Money;
  expenses_net: Money;
  transfers_in: Money;
  transfers_out: Money;
  adjustments_increase: Money;
  adjustments_decrease: Money;
  net_movement: Money;
  history: LedgerEntry[];
  categories: CategorySpend[];
  income_sources: CategorySpend[];
}

export interface LargeExpense {
  id: string;
  transaction_date: string;
  description: string;
  amount: Money;
  category_name: string | null;
  merchant_or_payee: string | null;
  threshold: Money;
  multiple_of_median: number;
}

export interface IncomeSource {
  name: string;
  amount: Money;
  percentage: number;
  transaction_count: number;
}

export interface RecurringCandidate {
  merchant_or_payee: string;
  category_name: string | null;
  transaction_count: number;
  average_amount: Money;
  amount_range_pct: number;
  last_seen: string;
  suggestion: string;
}

export interface AnalyticsReport {
  start_date: string;
  end_date: string;
  savings_rate_pct: number | null;
  savings_rate_definition: string;
  income: Money;
  expenses_net: Money;
  fixed_expenses: Money;
  variable_expenses: Money;
  essential_expenses: Money;
  discretionary_expenses: Money;
  budget_adherence_pct: number | null;
  budget_definition: string;
  category_concentration: CategorySpend[];
  top_category_share_pct: number | null;
  income_sources: IncomeSource[];
  large_expenses: LargeExpense[];
  large_expense_threshold: Money | null;
  recurring_candidates: RecurringCandidate[];
  spending_trend: MonthlyPoint[];
  definitions: Record<string, string>;
}

export interface Budget {
  id: string;
  category_id: string | null;
  category_name: string | null;
  category_color: string | null;
  period_type: "monthly";
  period_start: string;
  amount: Money;
  warning_threshold: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contribution {
  id: string;
  goal_id: string;
  amount: Money;
  contribution_date: string;
  note: string | null;
  created_at: string;
}

export interface Goal {
  id: string;
  name: string;
  target_amount: Money;
  current_amount: Money | null;
  remaining_amount: Money | null;
  progress_pct: number;
  target_date: string | null;
  status: GoalStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  contributions: Contribution[];
}

export interface CommitteeScheduleItem {
  month: string;
  installment_number: number;
  amount: Money;
  paid_amount: Money;
  status: "paid" | "upcoming";
  source: "prior" | "transaction" | null;
  is_current: boolean;
}

export interface Committee {
  id: string;
  name: string;
  monthly_amount: Money;
  start_month: string;
  end_month: string;
  prior_paid_installments: number;
  notes: string | null;
  total_installments: number;
  total_amount: Money;
  paid_installments: number;
  linked_paid_installments: number;
  total_paid: Money;
  remaining_installments: number;
  remaining_amount: Money;
  current_month: string;
  progress_pct: number;
  schedule: CommitteeScheduleItem[];
  created_at: string;
  updated_at: string;
}

export interface Recurring {
  id: string;
  name: string;
  transaction_type: TransactionType;
  amount: Money;
  account_id: string;
  account_name: string | null;
  category_id: string;
  category_name: string | null;
  category_color: string | null;
  description: string;
  merchant_or_payee: string | null;
  payment_method: string | null;
  notes: string | null;
  frequency: RecurringFrequency;
  interval_count: number;
  start_date: string;
  next_due_date: string;
  end_date: string | null;
  is_active: boolean;
  auto_post: boolean;
  created_at: string;
  updated_at: string;
  days_until_due: number | null;
}

export interface Occurrence {
  id: string;
  template_id: string;
  due_date: string;
  status: string;
  transaction_id: string | null;
  created_at: string;
}

export interface PostDueResult {
  created_count: number;
  skipped_count: number;
  transactions: string[];
  message: string;
}

export interface BaselineUsageItem {
  id: string;
  description: string;
  amount: Money;
  occurred_on: string | null;
  notes: string | null;
}

export interface BaselineAccount {
  id: string;
  account_id: string;
  account_name: string;
  currency: string;
  original_funds: Money;
  historical_usage: Money;
  opening_balance: Money;
  itemized_usage: Money;
  unclassified_usage: Money;
  usage_items: BaselineUsageItem[];
}

export interface Baseline {
  id: string;
  name: string;
  baseline_date: string;
  notes: string;
  total_original_funds: Money;
  total_historical_usage: Money;
  total_opening_balance: Money;
  accounts: BaselineAccount[];
  created_at: string;
  updated_at: string;
}

export interface ImportRowResult {
  row_number: number;
  values: Record<string, string>;
  normalized: Record<string, string | null> | null;
  errors: string[];
  is_duplicate: boolean;
  duplicate_reason: string | null;
  is_valid: boolean;
}

export interface ImportPreview {
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  rows: ImportRowResult[];
  detected_columns: string[];
  expected_columns: string[];
}

export interface ImportCommitResult {
  import_batch_id: string;
  filename: string;
  total_rows: number;
  created_count: number;
  skipped_count: number;
  rejected_count: number;
  errors: Array<Record<string, unknown>>;
}

export interface AuditLog {
  id: string;
  entity_type: string;
  entity_id: string | null;
  action: string;
  summary: string;
  changes: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

export interface SystemStatus {
  app_name: string;
  app_env: string;
  currency: string;
  auth_enabled: boolean;
  baseline_date: string;
  database_connected: boolean;
  version: string;
}

export interface BackupStatus {
  configured: boolean;
  pg_tools_available: boolean;
  can_backup: boolean;
  backup_needed: boolean;
  backup_running: boolean;
  source_host: string | null;
  source_database: string | null;
  target_host: string | null;
  target_database: string | null;
  last_backup_at: string | null;
  last_backup_file: string | null;
  last_backup_size_bytes: number | null;
  last_change_at: string | null;
  covered_through: string | null;
  message: string;
}

export interface BackupResult {
  backup_at: string;
  backup_file: string;
  size_bytes: number;
  duration_seconds: number;
  covered_through: string | null;
  target_database: string;
  counts: Record<string, number>;
}
