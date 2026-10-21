export const TXN_LABELS: Record<string, string> = {
  income: "Income",
  expense: "Expense",
  refund: "Refund",
  adjustment_increase: "Adjustment +",
  adjustment_decrease: "Adjustment −",
};

export const TXN_COLORS: Record<string, string> = {
  income: "text-emerald-700 bg-emerald-50 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900",
  expense: "text-rose-700 bg-rose-50 border-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-900",
  refund: "text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900",
  adjustment_increase:
    "text-sky-700 bg-sky-50 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900",
  adjustment_decrease:
    "text-violet-700 bg-violet-50 border-violet-200 dark:bg-violet-950 dark:text-violet-300 dark:border-violet-900",
};

export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  checking: "Checking",
  savings: "Savings",
  cash: "Cash",
  other: "Other",
};

export const FREQUENCY_LABELS: Record<string, string> = {
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

export const GOAL_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  completed: "Completed",
  paused: "Paused",
  cancelled: "Cancelled",
};

export const EXPENSE_NATURE_LABELS: Record<string, string> = {
  fixed: "Fixed",
  variable: "Variable",
  mixed: "Mixed",
};

export const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "LayoutDashboard", group: "Overview" },
  { href: "/transactions", label: "Transactions", icon: "ArrowLeftRight", group: "Money" },
  { href: "/transfers", label: "Transfers", icon: "Repeat2", group: "Money" },
  { href: "/reports", label: "Reports", icon: "ChartColumn", group: "Insights" },
  { href: "/budgets", label: "Budgets", icon: "Target", group: "Planning" },
  { href: "/goals", label: "Goals", icon: "Trophy", group: "Planning" },
  { href: "/recurring", label: "Recurring", icon: "CalendarClock", group: "Planning" },
  { href: "/import-export", label: "Import & Export", icon: "ArrowDownUp", group: "Data" },
  { href: "/settings", label: "Settings", icon: "Settings2", group: "Data" },
] as const;

export const CHART_COLORS = [
  "#2F6B57",
  "#C99A2E",
  "#4A7FA5",
  "#C05C4B",
  "#8264A8",
  "#5B8C6E",
  "#A9793F",
  "#5D7285",
];
