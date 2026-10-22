"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Activity,
  BadgeCheck,
  Banknote,
  CheckCircle2,
  CircleAlert,
  Database,
  Download,
  History,
  Landmark,
  Layers,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Tag,
  Trash2,
  WalletCards,
  X,
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
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
import { api, buildQuery, errorMessage } from "@/lib/api";
import {
  ACCOUNT_TYPE_LABELS,
  EXPENSE_NATURE_LABELS,
} from "@/lib/constants";
import { formatBytes, formatDate, formatDateTime, formatMoney, toNumber } from "@/lib/format";
import { useApi, useBackupStatus, useSystemStatus } from "@/lib/hooks";
import type {
  AccountType,
  AccountWithBalance,
  AuditLog,
  Baseline,
  Category,
  CategoryType,
  ExpenseNature,
  Page,
  SystemStatus,
  Transaction,
  Transfer,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const ACCOUNT_TYPES: AccountType[] = ["checking", "savings", "cash", "other"];
const CATEGORY_TYPES: CategoryType[] = ["income", "expense"];
const EXPENSE_NATURES: ExpenseNature[] = ["fixed", "variable", "mixed"];

const accountSchema = z.object({
  name: z.string().trim().min(1, "Enter an account name").max(80),
  account_type: z.enum(["checking", "savings", "cash", "other"]),
  currency: z.string().trim().length(3, "Use a 3-letter currency code"),
  opening_balance: z
    .string()
    .min(1, "Enter the opening balance")
    .refine((value) => Number(value) >= 0, "Cannot be negative"),
  opening_date: z.string().min(1, "Choose the opening date"),
  is_active: z.boolean(),
  notes: z.string().optional(),
});

const categorySchema = z.object({
  name: z.string().trim().min(1, "Enter a category name").max(80),
  category_type: z.enum(["income", "expense"]),
  parent_category_id: z.string().optional(),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex colour"),
  is_essential: z.boolean(),
  expense_nature: z.enum(["fixed", "variable", "mixed"]),
  sort_order: z
    .string()
    .refine((value) => Number.isInteger(Number(value)) && Number(value) >= 0, "Use 0 or more"),
  is_active: z.boolean(),
  notes: z.string().optional(),
});

type AccountValues = z.infer<typeof accountSchema>;
type CategoryValues = z.infer<typeof categorySchema>;

type DraftUsageItem = {
  key: string;
  description: string;
  amount: string;
  occurred_on: string;
  notes: string;
};

type DraftBaselineAccount = {
  account_id: string;
  account_name: string;
  original_funds: string;
  historical_usage: string;
  opening_balance: string;
  usage_items: DraftUsageItem[];
};

type BaselineDraft = {
  name: string;
  baseline_date: string;
  notes: string;
  accounts: DraftBaselineAccount[];
};

let draftKey = 0;
function nextKey(): string {
  draftKey += 1;
  return `usage-${draftKey}`;
}

function moneyNumber(value: string | number | null | undefined): number {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function toDraft(baseline: Baseline): BaselineDraft {
  return {
    name: baseline.name,
    baseline_date: baseline.baseline_date,
    notes: baseline.notes,
    accounts: baseline.accounts.map((account) => ({
      account_id: account.account_id,
      account_name: account.account_name,
      original_funds: account.original_funds,
      historical_usage: account.historical_usage,
      opening_balance: account.opening_balance,
      usage_items: account.usage_items.map((item) => ({
        key: item.id,
        description: item.description,
        amount: item.amount,
        occurred_on: item.occurred_on ?? "",
        notes: item.notes ?? "",
      })),
    })),
  };
}

export default function SettingsPage() {
  const [tab, setTab] = useState("accounts");
  const status = useSystemStatus();
  const baselineDate = status.data?.baseline_date;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        description="Manage the accounts and categories that make up your ledger, audit the starting position, and review the trail of every change."
        actions={
          <Pill className="border-border bg-card text-muted-foreground">
            <ShieldCheck className="size-3" />
            Single user · private
          </Pill>
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-9 w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="accounts">
            <WalletCards className="size-3.5" /> Accounts
          </TabsTrigger>
          <TabsTrigger value="categories">
            <Tag className="size-3.5" /> Categories
          </TabsTrigger>
          <TabsTrigger value="baseline">
            <History className="size-3.5" /> Baseline
          </TabsTrigger>
          <TabsTrigger value="audit">
            <Activity className="size-3.5" /> Audit log
          </TabsTrigger>
          <TabsTrigger value="system">
            <Settings2 className="size-3.5" /> System
          </TabsTrigger>
        </TabsList>

        <TabsContent value="accounts" className="mt-4">
          <AccountsTab baselineDate={baselineDate} />
        </TabsContent>
        <TabsContent value="categories" className="mt-4">
          <CategoriesTab />
        </TabsContent>
        <TabsContent value="baseline" className="mt-4">
          <BaselineTab />
        </TabsContent>
        <TabsContent value="audit" className="mt-4">
          <AuditTab />
        </TabsContent>
        <TabsContent value="system" className="mt-4">
          <SystemTab status={status.data} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AccountsTab({ baselineDate }: { baselineDate?: string }) {
  const { data, loading, error, refresh } = useApi<AccountWithBalance[]>("/accounts");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AccountWithBalance | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AccountWithBalance | null>(null);

  const form = useForm<AccountValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      name: "",
      account_type: "checking",
      currency: "PKR",
      opening_balance: "0",
      opening_date: baselineDate ?? new Date().toISOString().slice(0, 10),
      is_active: true,
      notes: "",
    },
  });

  const accounts = data ?? [];
  const active = accounts.filter((account) => account.is_active);
  const total = accounts.reduce((sum, account) => sum + toNumber(account.current_balance), 0);

  const openCreate = () => {
    setEditing(null);
    form.reset({
      name: "",
      account_type: "checking",
      currency: "PKR",
      opening_balance: "0",
      opening_date: baselineDate ?? new Date().toISOString().slice(0, 10),
      is_active: true,
      notes: "",
    });
    setOpen(true);
  };

  const openEdit = (account: AccountWithBalance) => {
    setEditing(account);
    form.reset({
      name: account.name,
      account_type: account.account_type,
      currency: account.currency,
      opening_balance: account.opening_balance,
      opening_date: account.opening_date,
      is_active: account.is_active,
      notes: account.notes ?? "",
    });
    setOpen(true);
  };

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name.trim(),
      account_type: values.account_type,
      currency: values.currency.toUpperCase(),
      opening_balance: values.opening_balance,
      opening_date: values.opening_date,
      is_active: values.is_active,
      notes: values.notes?.trim() || null,
    };
    try {
      if (editing) {
        await api(`/accounts/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Account updated");
      } else {
        await api("/accounts", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Account created");
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
      await api(`/accounts/${deleteTarget.id}`, { method: "DELETE" });
      toast.success("Account deleted");
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
      setDeleteTarget(null);
    }
  };

  const toggleActive = async (account: AccountWithBalance) => {
    try {
      await api(`/accounts/${account.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !account.is_active }),
      });
      toast.success(account.is_active ? "Account deactivated" : "Account reactivated");
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Combined balance"
          value={formatMoney(total)}
          icon={Landmark}
          hint={`${accounts.length} account${accounts.length === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Active accounts"
          value={String(active.length)}
          icon={BadgeCheck}
          tone="positive"
          hint={`${accounts.length - active.length} inactive`}
        />
        <StatCard
          label="Baseline date"
          value={baselineDate ? formatDate(baselineDate, "d MMM yyyy") : "—"}
          icon={History}
          tone="gold"
          hint="Opening balances start here"
        />
      </div>

      <div className="surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
          <SectionHeading
            title="Ledger accounts"
            description="Balances include every recorded transaction and transfer. Deactivate an account to retire it without touching history."
          />
          <Button size="sm" onClick={openCreate}>
            <Plus className="size-3.5" /> New account
          </Button>
        </div>

        {error ? <ErrorState message={error} onRetry={refresh} /> : null}
        {loading ? (
          <div className="p-4">
            <LoadingBlock rows={4} />
          </div>
        ) : accounts.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Opening</TableHead>
                <TableHead className="text-right">Current balance</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <span className="flex size-8 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                        <Banknote className="size-4" />
                      </span>
                      <div>
                        <p className="font-medium text-foreground">{account.name}</p>
                        <p className="text-[11px] text-muted-foreground">
                          Opened {formatDate(account.opening_date)} · {account.currency}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {ACCOUNT_TYPE_LABELS[account.account_type] ?? account.account_type}
                  </TableCell>
                  <TableCell className="money text-right">{formatMoney(account.opening_balance)}</TableCell>
                  <TableCell className="money text-right font-medium">
                    {formatMoney(account.current_balance)}
                  </TableCell>
                  <TableCell>
                    <button type="button" onClick={() => toggleActive(account)} title="Toggle active">
                      <Pill
                        className={
                          account.is_active
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                            : "border-border bg-muted text-muted-foreground"
                        }
                      >
                        {account.is_active ? "Active" : "Inactive"}
                      </Pill>
                    </button>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-0.5">
                      <Button size="icon-sm" variant="ghost" title="Edit account" onClick={() => openEdit(account)}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title="Delete account"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(account)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState
            icon={WalletCards}
            title="No accounts yet"
            description="Create your first account to start recording income and expenses."
            action={
              <Button size="sm" onClick={openCreate}>
                <Plus className="size-3.5" /> New account
              </Button>
            }
          />
        )}
      </div>

      <DefinitionNote>
        An account with ledger history cannot be deleted; deactivate it instead so past reports stay
        intact. If you use a baseline snapshot, edit its accounts on the Baseline tab so original
        funds, historical usage and the opening balance keep reconciling. Otherwise edit the opening
        balance here.
      </DefinitionNote>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit account" : "New account"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Changes are audited. Renaming an account updates every report."
                : "Opening balance is the amount already in the account on its opening date."}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Name" required htmlFor="account-name" error={form.formState.errors.name?.message}>
              <Input id="account-name" placeholder="e.g. salary-M" {...form.register("name")} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Type" htmlFor="account-type">
                <NativeSelect
                  id="account-type"
                  value={form.watch("account_type")}
                  onChange={(value) => form.setValue("account_type", value as AccountType)}
                  options={ACCOUNT_TYPES.map((type) => ({
                    value: type,
                    label: ACCOUNT_TYPE_LABELS[type] ?? type,
                  }))}
                />
              </Field>
              <Field label="Currency" htmlFor="account-currency" error={form.formState.errors.currency?.message}>
                <Input id="account-currency" maxLength={3} {...form.register("currency")} />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Opening balance (PKR)"
                required
                htmlFor="account-opening"
                error={form.formState.errors.opening_balance?.message}
              >
                <Input
                  id="account-opening"
                  type="number"
                  step="0.01"
                  min="0"
                  {...form.register("opening_balance")}
                />
              </Field>
              <Field
                label="Opening date"
                required
                htmlFor="account-opening-date"
                error={form.formState.errors.opening_date?.message}
              >
                <Input id="account-opening-date" type="date" {...form.register("opening_date")} />
              </Field>
            </div>
            <Field label="Notes" htmlFor="account-notes">
              <Textarea id="account-notes" rows={2} placeholder="Optional" {...form.register("notes")} />
            </Field>
            <label className="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" className="size-4 accent-primary" {...form.register("is_active")} />
              Active — include in day-to-day entry and reports
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(value) => !value && setDeleteTarget(null)}
        title="Delete this account?"
        description={
          deleteTarget
            ? `${deleteTarget.name} will be removed permanently. Accounts with ledger history are protected and must be deactivated instead.`
            : ""
        }
        confirmLabel="Delete account"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}

function CategoriesTab() {
  const { data, loading, error, refresh } = useApi<Category[]>("/categories?include_inactive=true");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null);
  const [filter, setFilter] = useState<"all" | CategoryType>("all");

  const form = useForm<CategoryValues>({
    resolver: zodResolver(categorySchema),
    defaultValues: {
      name: "",
      category_type: "expense",
      parent_category_id: "",
      color: "#2F6B57",
      is_essential: true,
      expense_nature: "variable",
      sort_order: "0",
      is_active: true,
      notes: "",
    },
  });

  const categories = data ?? [];
  const visible = filter === "all" ? categories : categories.filter((row) => row.category_type === filter);
  const selectedType = form.watch("category_type");
  const parentOptions = categories
    .filter((row) => row.category_type === selectedType && row.id !== editing?.id)
    .sort((a, b) => a.name.localeCompare(b.name));

  const openCreate = () => {
    setEditing(null);
    form.reset({
      name: "",
      category_type: "expense",
      parent_category_id: "",
      color: "#2F6B57",
      is_essential: true,
      expense_nature: "variable",
      sort_order: "0",
      is_active: true,
      notes: "",
    });
    setOpen(true);
  };

  const openEdit = (category: Category) => {
    setEditing(category);
    form.reset({
      name: category.name,
      category_type: category.category_type,
      parent_category_id: category.parent_category_id ?? "",
      color: category.color,
      is_essential: category.is_essential,
      expense_nature: category.expense_nature,
      sort_order: String(category.sort_order),
      is_active: category.is_active,
      notes: category.notes ?? "",
    });
    setOpen(true);
  };

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      name: values.name.trim(),
      category_type: values.category_type,
      parent_category_id: values.parent_category_id || null,
      color: values.color,
      is_essential: values.is_essential,
      expense_nature: values.expense_nature,
      sort_order: Number(values.sort_order),
      is_active: values.is_active,
      notes: values.notes?.trim() || null,
    };
    try {
      if (editing) {
        await api(`/categories/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Category updated");
      } else {
        await api("/categories", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Category created");
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
      const result = await api<{ deactivated: boolean; message: string }>(
        `/categories/${deleteTarget.id}`,
        { method: "DELETE" }
      );
      toast.success(result.message);
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
          <SectionHeading
            title="Categories"
            description="Income and expense categories power reports, budgets and recurring templates."
          />
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
              {(["all", "expense", "income"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilter(value)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] font-medium capitalize transition-colors",
                    filter === value
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {value}
                </button>
              ))}
            </div>
            <Button size="sm" onClick={openCreate}>
              <Plus className="size-3.5" /> New category
            </Button>
          </div>
        </div>

        {error ? <ErrorState message={error} onRetry={refresh} /> : null}
        {loading ? (
          <div className="p-4">
            <LoadingBlock rows={5} />
          </div>
        ) : visible.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Nature</TableHead>
                <TableHead className="text-center">Essential</TableHead>
                <TableHead className="text-right">Used by</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((category) => (
                <TableRow key={category.id}>
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <span
                        className="size-3 rounded-full border border-black/10"
                        style={{ backgroundColor: category.color }}
                      />
                      <div>
                        <p className="font-medium text-foreground">{category.name}</p>
                        {category.parent_name ? (
                          <p className="text-[11px] text-muted-foreground">under {category.parent_name}</p>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="capitalize text-muted-foreground">{category.category_type}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {category.category_type === "expense"
                      ? EXPENSE_NATURE_LABELS[category.expense_nature] ?? category.expense_nature
                      : "—"}
                  </TableCell>
                  <TableCell className="text-center text-muted-foreground">
                    {category.is_essential ? "Yes" : "No"}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {category.transaction_count} txn{category.transaction_count === 1 ? "" : "s"}
                  </TableCell>
                  <TableCell>
                    <Pill
                      className={
                        category.is_active
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                          : "border-border bg-muted text-muted-foreground"
                      }
                    >
                      {category.is_active ? "Active" : "Inactive"}
                    </Pill>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-0.5">
                      <Button size="icon-sm" variant="ghost" title="Edit category" onClick={() => openEdit(category)}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title="Delete category"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(category)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState
            icon={Tag}
            title="No categories in this view"
            description="Add categories for the kinds of income and spending you track."
            action={
              <Button size="sm" onClick={openCreate}>
                <Plus className="size-3.5" /> New category
              </Button>
            }
          />
        )}
      </div>

      <DefinitionNote>
        Categories used by transactions, budgets or recurring templates are deactivated instead of
        deleted, so history and reports stay readable. Type changes are blocked while transactions
        reference the category.
      </DefinitionNote>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit category" : "New category"}</DialogTitle>
            <DialogDescription>
              Essential and nature flags drive the analytics breakdown of essential vs discretionary
              and fixed vs variable spending.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-[1fr_130px]">
              <Field label="Name" required htmlFor="category-name" error={form.formState.errors.name?.message}>
                <Input id="category-name" placeholder="e.g. Groceries" {...form.register("name")} />
              </Field>
              <Field label="Type" htmlFor="category-type">
                <NativeSelect
                  id="category-type"
                  value={form.watch("category_type")}
                  onChange={(value) => {
                    form.setValue("category_type", value as CategoryType);
                    form.setValue("parent_category_id", "");
                  }}
                  options={CATEGORY_TYPES.map((type) => ({
                    value: type,
                    label: type === "income" ? "Income" : "Expense",
                  }))}
                />
              </Field>
            </div>
            <Field label="Parent category" htmlFor="category-parent" hint="Optional grouping for reports">
              <NativeSelect
                id="category-parent"
                value={form.watch("parent_category_id") ?? ""}
                onChange={(value) => form.setValue("parent_category_id", value)}
                options={parentOptions.map((category) => ({
                  value: category.id,
                  label: category.name,
                }))}
                placeholder="No parent"
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Colour" htmlFor="category-color" error={form.formState.errors.color?.message}>
                <div className="flex items-center gap-2">
                  <input
                    id="category-color"
                    type="color"
                    className="h-9 w-12 cursor-pointer rounded-lg border border-input bg-background p-1"
                    value={form.watch("color")}
                    onChange={(event) => form.setValue("color", event.target.value.toUpperCase())}
                  />
                  <Input className="font-mono text-xs" {...form.register("color")} />
                </div>
              </Field>
              <Field label="Sort order" htmlFor="category-order" error={form.formState.errors.sort_order?.message}>
                <Input id="category-order" type="number" min="0" step="1" {...form.register("sort_order")} />
              </Field>
              <Field label="Nature" htmlFor="category-nature">
                <NativeSelect
                  id="category-nature"
                  value={form.watch("expense_nature")}
                  onChange={(value) => form.setValue("expense_nature", value as ExpenseNature)}
                  options={EXPENSE_NATURES.map((nature) => ({
                    value: nature,
                    label: EXPENSE_NATURE_LABELS[nature] ?? nature,
                  }))}
                />
              </Field>
            </div>
            <Field label="Notes" htmlFor="category-notes">
              <Textarea id="category-notes" rows={2} placeholder="Optional" {...form.register("notes")} />
            </Field>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-xs text-foreground">
                <input type="checkbox" className="size-4 accent-primary" {...form.register("is_essential")} />
                Essential spending
              </label>
              <label className="flex items-center gap-2 text-xs text-foreground">
                <input type="checkbox" className="size-4 accent-primary" {...form.register("is_active")} />
                Active
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {editing ? "Save changes" : "Create category"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(value) => !value && setDeleteTarget(null)}
        title="Delete this category?"
        description={
          deleteTarget
            ? `${deleteTarget.name} will be deleted if unused. If transactions, budgets or recurring entries reference it, it will be deactivated instead.`
            : ""
        }
        confirmLabel="Delete category"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}

function BaselineTab() {
  const { data, loading, error, refresh } = useApi<Baseline>("/baseline");

  if (loading) return <LoadingBlock rows={5} />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) {
    return (
      <EmptyState
        icon={History}
        title="No baseline configured"
        description="Run the seed command to create the initial baseline."
      />
    );
  }

  // Remount after a successful save so the editor picks up server values
  // without an effect that copies props into state.
  return <BaselineEditor key={data.updated_at} baseline={data} onSaved={refresh} />;
}

function BaselineEditor({ baseline, onSaved }: { baseline: Baseline; onSaved: () => void }) {
  const [draft, setDraft] = useState<BaselineDraft>(() => toDraft(baseline));
  const [saving, setSaving] = useState(false);

  const validation = useMemo(() => {
    const issues: string[] = [];
    if (!draft.name.trim()) issues.push("Baseline name is required.");
    if (!draft.baseline_date) issues.push("Baseline date is required.");
    if (!draft.notes.trim()) issues.push("Audit notes are required.");
    const seen = new Set<string>();
    for (const account of draft.accounts) {
      if (seen.has(account.account_id)) issues.push(`${account.account_name} appears twice.`);
      seen.add(account.account_id);
      const original = moneyNumber(account.original_funds);
      const usage = moneyNumber(account.historical_usage);
      const opening = moneyNumber(account.opening_balance);
      if (Math.abs(original - usage - opening) > 0.005) {
        issues.push(`${account.account_name}: original funds must equal usage + opening.`);
      }
      let itemized = 0;
      for (const item of account.usage_items) {
        const amount = moneyNumber(item.amount);
        itemized += amount;
        if (!item.description.trim()) issues.push(`${account.account_name}: every usage item needs a description.`);
        if (amount <= 0) issues.push(`${account.account_name}: usage item amounts must be positive.`);
      }
      if (itemized > usage + 0.005) {
        issues.push(`${account.account_name}: itemized usage exceeds total historical usage.`);
      }
    }
    return { valid: issues.length === 0, issues };
  }, [draft]);

  const totals = useMemo(() => {
    let original = 0;
    let usage = 0;
    let opening = 0;
    let itemized = 0;
    for (const account of draft.accounts) {
      original += moneyNumber(account.original_funds);
      usage += moneyNumber(account.historical_usage);
      opening += moneyNumber(account.opening_balance);
      for (const item of account.usage_items) itemized += moneyNumber(item.amount);
    }
    return { original, usage, opening, itemized };
  }, [draft]);

  const updateAccount = (accountId: string, patch: Partial<DraftBaselineAccount>) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            accounts: current.accounts.map((account) =>
              account.account_id === accountId ? { ...account, ...patch } : account
            ),
          }
        : current
    );
  };

  const updateItem = (accountId: string, key: string, patch: Partial<DraftUsageItem>) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            accounts: current.accounts.map((account) =>
              account.account_id === accountId
                ? {
                    ...account,
                    usage_items: account.usage_items.map((item) =>
                      item.key === key ? { ...item, ...patch } : item
                    ),
                  }
                : account
            ),
          }
        : current
    );
  };

  const addItem = (accountId: string) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            accounts: current.accounts.map((account) =>
              account.account_id === accountId
                ? {
                    ...account,
                    usage_items: [
                      ...account.usage_items,
                      { key: nextKey(), description: "", amount: "", occurred_on: "", notes: "" },
                    ],
                  }
                : account
            ),
          }
        : current
    );
  };

  const removeItem = (accountId: string, key: string) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            accounts: current.accounts.map((account) =>
              account.account_id === accountId
                ? {
                    ...account,
                    usage_items: account.usage_items.filter((item) => item.key !== key),
                  }
                : account
            ),
          }
        : current
    );
  };

  const save = async () => {
    if (!validation.valid) {
      toast.error(validation.issues[0] ?? "Fix the baseline before saving.");
      return;
    }
    setSaving(true);
    try {
      await api("/baseline", {
        method: "PUT",
        body: JSON.stringify({
          name: draft.name.trim(),
          baseline_date: draft.baseline_date,
          notes: draft.notes.trim(),
          accounts: draft.accounts.map((account) => ({
            account_id: account.account_id,
            original_funds: account.original_funds,
            historical_usage: account.historical_usage,
            opening_balance: account.opening_balance,
            usage_items: account.usage_items.map((item) => ({
              description: item.description.trim(),
              amount: item.amount,
              occurred_on: item.occurred_on || null,
              notes: item.notes.trim() || null,
            })),
          })),
        }),
      });
      toast.success("Baseline updated");
      onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Original funds" value={formatMoney(totals.original)} icon={Layers} hint="Across all accounts" />
        <StatCard label="Historical usage" value={formatMoney(totals.usage)} icon={History} tone="gold" hint={`${formatMoney(totals.itemized)} itemized`} />
        <StatCard label="Opening balances" value={formatMoney(totals.opening)} icon={Landmark} tone="positive" hint="Starting ledger position" />
        <StatCard label="Unclassified usage" value={formatMoney(Math.max(totals.usage - totals.itemized, 0))} icon={CircleAlert} hint="Not itemized" />
      </div>

      <div className="surface p-4 sm:p-5">
        <SectionHeading
          title="Baseline snapshot"
          description="The baseline is the historical position before tracking began. It is never counted as income or expenses."
          action={
            <Button size="sm" onClick={save} disabled={saving || !validation.valid}>
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              Save baseline
            </Button>
          }
        />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_180px]">
          <Field label="Snapshot name" htmlFor="baseline-name">
            <Input
              id="baseline-name"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
          </Field>
          <Field label="Baseline date" htmlFor="baseline-date">
            <Input
              id="baseline-date"
              type="date"
              value={draft.baseline_date}
              onChange={(event) => setDraft({ ...draft, baseline_date: event.target.value })}
            />
          </Field>
        </div>
        <div className="mt-3">
          <Field
            label="Audit notes"
            htmlFor="baseline-notes"
            hint="Required. Explain why this starting position is accurate."
          >
            <Textarea
              id="baseline-notes"
              rows={2}
              value={draft.notes}
              onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
            />
          </Field>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
          The baseline date is also the opening date for every account. It cannot move past recorded
          transactions or transfers; delete or move those entries first.
        </p>
      </div>

      {!validation.valid ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300">
          <p className="font-medium">Fix before saving</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {validation.issues.slice(0, 6).map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-3">
        {draft.accounts.map((account) => {
          const original = moneyNumber(account.original_funds);
          const usage = moneyNumber(account.historical_usage);
          const opening = moneyNumber(account.opening_balance);
          const reconciles = Math.abs(original - usage - opening) <= 0.005;
          const itemized = account.usage_items.reduce((sum, item) => sum + moneyNumber(item.amount), 0);
          return (
            <div key={account.account_id} className="surface flex flex-col p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-heading text-sm font-semibold">{account.account_name}</h3>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {formatMoney(itemized)} itemized of {formatMoney(usage)} used
                  </p>
                </div>
                <Pill
                  className={
                    reconciles
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                      : "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
                  }
                >
                  {reconciles ? <BadgeCheck className="size-2.5" /> : <CircleAlert className="size-2.5" />}
                  {reconciles ? "Reconciles" : "Check"}
                </Pill>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2">
                <Field label="Original funds" htmlFor={`original-${account.account_id}`}>
                  <Input
                    id={`original-${account.account_id}`}
                    type="number"
                    step="0.01"
                    min="0"
                    value={account.original_funds}
                    onChange={(event) => updateAccount(account.account_id, { original_funds: event.target.value })}
                  />
                </Field>
                <Field label="Usage" htmlFor={`usage-${account.account_id}`}>
                  <Input
                    id={`usage-${account.account_id}`}
                    type="number"
                    step="0.01"
                    min="0"
                    value={account.historical_usage}
                    onChange={(event) =>
                      updateAccount(account.account_id, { historical_usage: event.target.value })
                    }
                  />
                </Field>
                <Field label="Opening" htmlFor={`opening-${account.account_id}`}>
                  <Input
                    id={`opening-${account.account_id}`}
                    type="number"
                    step="0.01"
                    min="0"
                    value={account.opening_balance}
                    onChange={(event) =>
                      updateAccount(account.account_id, { opening_balance: event.target.value })
                    }
                  />
                </Field>
              </div>

              <p className="mt-2 text-[11px] text-muted-foreground">
                {formatMoney(original)} − {formatMoney(usage)} = {formatMoney(original - usage)}
                {reconciles ? " · matches opening" : " · does not match opening"}
              </p>

              <div className="mt-4 flex items-center justify-between">
                <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  Itemized usage
                </p>
                <Button size="xs" variant="outline" onClick={() => addItem(account.account_id)}>
                  <Plus className="size-3" /> Add item
                </Button>
              </div>

              <div className="mt-2 space-y-2">
                {account.usage_items.length ? (
                  account.usage_items.map((item) => (
                    <div key={item.key} className="rounded-lg border border-border/70 bg-muted/20 p-2">
                      <div className="flex items-start gap-2">
                        <Input
                          aria-label="Usage description"
                          placeholder="What was it spent on?"
                          value={item.description}
                          onChange={(event) =>
                            updateItem(account.account_id, item.key, { description: event.target.value })
                          }
                          className="h-8 flex-1"
                        />
                        <Input
                          aria-label="Usage amount"
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="0.00"
                          value={item.amount}
                          onChange={(event) =>
                            updateItem(account.account_id, item.key, { amount: event.target.value })
                          }
                          className="h-8 w-24"
                        />
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          title="Remove item"
                          onClick={() => removeItem(account.account_id, item.key)}
                        >
                          <X className="size-3" />
                        </Button>
                      </div>
                      <div className="mt-1.5 flex gap-2">
                        <Input
                          aria-label="Usage date"
                          type="date"
                          value={item.occurred_on}
                          onChange={(event) =>
                            updateItem(account.account_id, item.key, { occurred_on: event.target.value })
                          }
                          className="h-7 flex-1 text-[11px]"
                        />
                        <Input
                          aria-label="Usage notes"
                          placeholder="Note (optional)"
                          value={item.notes}
                          onChange={(event) =>
                            updateItem(account.account_id, item.key, { notes: event.target.value })
                          }
                          className="h-7 flex-1 text-[11px]"
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="rounded-lg border border-dashed border-border px-3 py-3 text-center text-[11px] text-muted-foreground">
                    No itemized usage. The full amount stays unclassified.
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <DefinitionNote>
        Historical usage explains what happened to money before the baseline date (for example a
        laptop or committee payment). It is shown here for context only and never appears in monthly
        income, expense or category reports. Original funds must equal historical usage plus opening
        balance for every account.
      </DefinitionNote>
    </div>
  );
}

function AuditTab() {
  const [page, setPage] = useState(1);
  const [entity, setEntity] = useState("all");
  const query = buildQuery({
    page,
    page_size: 25,
    entity_type: entity === "all" ? undefined : entity,
  });
  const { data, loading, error, refresh } = useApi<Page<AuditLog>>(`/audit-logs${query}`);

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <div className="surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
          <SectionHeading
            title="Audit log"
            description="Every create, update, delete, import and baseline change is recorded with its before/after values."
          />
          <div className="flex items-center gap-2">
            <NativeSelect
              aria-label="Filter by entity"
              className="h-8 w-[150px]"
              value={entity}
              onChange={(value) => {
                setEntity(value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "All entities" },
                { value: "account", label: "Accounts" },
                { value: "category", label: "Categories" },
                { value: "transaction", label: "Transactions" },
                { value: "transfer", label: "Transfers" },
                { value: "budget", label: "Budgets" },
                { value: "goal", label: "Goals" },
                { value: "committee", label: "Committees" },
                { value: "recurring", label: "Recurring" },
                { value: "baseline", label: "Baseline" },
                { value: "import", label: "Imports" },
              ]}
            />
            <Button size="icon-sm" variant="outline" title="Refresh" onClick={refresh}>
              <RefreshCw className="size-3.5" />
            </Button>
          </div>
        </div>

        {error ? <ErrorState message={error} onRetry={refresh} /> : null}
        {loading ? (
          <div className="p-4">
            <LoadingBlock rows={6} />
          </div>
        ) : items.length ? (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </TableCell>
                    <TableCell>
                      <Pill className="border-border bg-muted capitalize text-muted-foreground">
                        {log.entity_type}
                      </Pill>
                    </TableCell>
                    <TableCell className="text-xs capitalize text-muted-foreground">{log.action}</TableCell>
                    <TableCell className="max-w-[560px]">
                      <p className="truncate text-xs text-foreground">{log.summary}</p>
                      {log.changes ? (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">
                            View changes
                          </summary>
                          <pre className="mt-1 max-h-56 overflow-auto rounded-lg border border-border/70 bg-muted/30 p-2 text-[10px] leading-4 text-muted-foreground">
                            {JSON.stringify(log.changes, null, 2)}
                          </pre>
                        </details>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between gap-2 border-t border-border/70 px-4 py-2.5 text-[11px] text-muted-foreground">
              <span>
                Page {meta?.page ?? 1} of {meta?.total_pages ?? 1} · {meta?.total ?? items.length} entries
              </span>
              <div className="flex items-center gap-2">
                <Button size="xs" variant="outline" disabled={page <= 1} onClick={() => setPage((value) => Math.max(value - 1, 1))}>
                  Previous
                </Button>
                <Button
                  size="xs"
                  variant="outline"
                  disabled={!meta || page >= meta.total_pages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            icon={Activity}
            title="No audit entries yet"
            description="Changes you make in the app will show up here with a timestamp and before/after values."
          />
        )}
      </div>
    </div>
  );
}

function BackupCard() {
  const { data, loading, error, backingUp, backupNow, refresh } = useBackupStatus();
  const running = backingUp || Boolean(data?.backup_running);

  const handleBackup = async () => {
    try {
      const result = await backupNow();
      const transactionCount = result.counts.transactions ?? 0;
      toast.success("Supabase backup saved", {
        description: `${transactionCount} transactions copied to ${result.target_database} (${formatBytes(result.size_bytes)}).`,
      });
    } catch (backupError) {
      toast.error(errorMessage(backupError));
    }
  };

  const stateTone = !data
    ? "border-border bg-muted/40 text-muted-foreground"
    : !data.can_backup
      ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300"
      : data.backup_needed
        ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300"
        : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300";

  return (
    <div className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeading
          title="Supabase backup"
          description="Copy the main local PostgreSQL database to Supabase for off-site recovery."
        />
        <div className="flex items-center gap-2">
          <Pill className={stateTone}>
            {data?.backup_needed ? (
              <CircleAlert className="size-2.5" />
            ) : (
              <CheckCircle2 className="size-2.5" />
            )}
            {!data ? "Checking" : data.backup_needed ? "Backup recommended" : "Up to date"}
          </Pill>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={refresh}
            disabled={loading}
            aria-label="Refresh backup status"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </Button>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        {error ?? data?.message ?? "Checking the Supabase backup status…"}
      </p>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Main database</dt>
          <dd className="mt-1 truncate text-xs font-medium">
            {data?.source_host
              ? `${data.source_host}/${data.source_database ?? ""}`
              : "—"}
          </dd>
        </div>
        <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Supabase target</dt>
          <dd className="mt-1 truncate text-xs font-medium">
            {data?.target_host
              ? `${data.target_host}/${data.target_database ?? ""}`
              : "Not configured"}
          </dd>
        </div>
        <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Last backup</dt>
          <dd className="mt-1 truncate text-xs font-medium">
            {data?.last_backup_at ? formatDateTime(data.last_backup_at) : "Never"}
          </dd>
        </div>
        <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Latest change</dt>
          <dd className="mt-1 truncate text-xs font-medium">
            {data?.last_change_at ? formatDateTime(data.last_change_at) : "—"}
          </dd>
        </div>
      </dl>

      {data?.last_backup_file ? (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Latest file: <span className="font-mono">{data.last_backup_file}</span> ·{" "}
          {formatBytes(data.last_backup_size_bytes)}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={handleBackup} disabled={!data?.can_backup || running}>
          {running ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
          {running ? "Backing up…" : "Back up now"}
        </Button>
        <p className="text-[11px] leading-5 text-muted-foreground">
          Creates a dated dump in <span className="font-mono">backups/</span> and restores it into
          Supabase. The main local database is not changed.
        </p>
      </div>
    </div>
  );
}

function SystemTab({ status }: { status: SystemStatus | null }) {
  const transactions = useApi<Page<Transaction>>("/transactions?page=1&page_size=1");
  const transfers = useApi<Page<Transfer>>("/transfers?page=1&page_size=1");
  const accounts = useApi<AccountWithBalance[]>("/accounts");
  const categories = useApi<Category[]>("/categories?include_inactive=true");

  const rows = [
    {
      label: "Environment",
      value: status?.app_env ?? "—",
      icon: Settings2,
      hint: status?.app_name ?? "Personal finance API",
    },
    {
      label: "Database",
      value: status?.database_connected ? "Connected" : "Unavailable",
      icon: Database,
      hint: "PostgreSQL · NUMERIC(14,2) money",
    },
    {
      label: "Currency",
      value: status?.currency ?? "PKR",
      icon: Banknote,
      hint: "All amounts are stored as decimals",
    },
    {
      label: "API auth",
      value: status?.auth_enabled ? "Bearer token" : "Local only",
      icon: ShieldCheck,
      hint: status?.auth_enabled ? "Token injected by the server proxy" : "Set API_AUTH_TOKEN to enable",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {rows.map((row) => (
          <StatCard
            key={row.label}
            label={row.label}
            value={row.value}
            hint={row.hint}
            icon={row.icon}
            tone={row.label === "Database" && status?.database_connected ? "positive" : "default"}
          />
        ))}
      </div>

      <BackupCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="surface p-4 sm:p-5">
          <SectionHeading
            title="Ledger footprint"
            description="A quick read on how much history this workspace holds."
          />
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
              <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Accounts</dt>
              <dd className="money mt-1 text-xl font-semibold">{accounts.data?.length ?? "—"}</dd>
            </div>
            <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
              <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Categories</dt>
              <dd className="money mt-1 text-xl font-semibold">{categories.data?.length ?? "—"}</dd>
            </div>
            <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
              <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Transactions</dt>
              <dd className="money mt-1 text-xl font-semibold">
                {transactions.data?.meta.total ?? "—"}
              </dd>
            </div>
            <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
              <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Transfers</dt>
              <dd className="money mt-1 text-xl font-semibold">{transfers.data?.meta.total ?? "—"}</dd>
            </div>
          </dl>
          <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
            Soft-deleted rows are excluded from these counts. Transfers are single atomic entries and
            never appear as income or expenses.
          </p>
        </div>

        <div className="surface p-4 sm:p-5">
          <SectionHeading
            title="How this workspace works"
            description="The rules that keep reports trustworthy."
          />
          <ul className="mt-4 space-y-2.5 text-xs leading-5 text-muted-foreground">
            <li className="flex gap-2">
              <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Money is stored as PostgreSQL <span className="font-mono">NUMERIC(14,2)</span> and never
              as floating point.
            </li>
            <li className="flex gap-2">
              <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Transfers keep the combined balance unchanged and are excluded from income and spending.
            </li>
            <li className="flex gap-2">
              <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Refunds reduce the category of the linked expense; adjustments affect balances only.
            </li>
            <li className="flex gap-2">
              <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Historical usage from the baseline is context, never monthly income or expense.
            </li>
            <li className="flex gap-2">
              <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
              Deletes are soft for transactions and transfers, so reports can be audited.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
