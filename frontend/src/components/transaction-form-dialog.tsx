"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

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
import { Field, NativeSelect } from "@/components/select-field";
import { api, errorMessage } from "@/lib/api";
import { TXN_LABELS } from "@/lib/constants";
import { formatMoney, toNumber } from "@/lib/format";
import { categoriesByType, useApi, useReferenceData } from "@/lib/hooks";
import type { Page, Transaction, TransactionType } from "@/lib/types";

const TXN_TYPES: TransactionType[] = [
  "expense",
  "income",
  "refund",
  "adjustment_increase",
  "adjustment_decrease",
];

const schema = z
  .object({
    transaction_date: z.string().min(1, "Choose a date"),
    transaction_type: z.enum([
      "income",
      "expense",
      "refund",
      "adjustment_increase",
      "adjustment_decrease",
    ]),
    amount: z
      .string()
      .min(1, "Enter an amount")
      .refine((value) => Number(value) > 0, "Amount must be greater than zero")
      .refine((value) => Number.isFinite(Number(value)), "Enter a valid number"),
    account_id: z.string().min(1, "Choose an account"),
    category_id: z.string().optional(),
    description: z.string().trim().min(1, "Add a short description").max(255),
    merchant_or_payee: z.string().max(160).optional(),
    payment_method: z.string().max(60).optional(),
    notes: z.string().optional(),
    related_transaction_id: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.transaction_type === "income" || values.transaction_type === "expense") {
      if (!values.category_id) {
        ctx.addIssue({
          code: "custom",
          path: ["category_id"],
          message: "Choose a category",
        });
      }
    }
    if (values.transaction_type === "refund" && !values.related_transaction_id) {
      ctx.addIssue({
        code: "custom",
        path: ["related_transaction_id"],
        message: "Choose the original expense being refunded",
      });
    }
  });

type FormValues = z.infer<typeof schema>;

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultsFor(transaction?: Transaction | null): FormValues {
  return {
    transaction_date: transaction?.transaction_date ?? todayISO(),
    transaction_type: transaction?.transaction_type ?? "expense",
    amount: transaction?.amount ?? "",
    account_id: transaction?.account_id ?? "",
    category_id: transaction?.category_id ?? "",
    description: transaction?.description ?? "",
    merchant_or_payee: transaction?.merchant_or_payee ?? "",
    payment_method: transaction?.payment_method ?? "",
    notes: transaction?.notes ?? "",
    related_transaction_id: transaction?.related_transaction_id ?? "",
  };
}

export function TransactionFormDialog({
  open,
  onOpenChange,
  transaction,
  onSaved,
  defaultType = "expense",
  defaultAccountId,
  defaultRelatedId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transaction?: Transaction | null;
  onSaved?: () => void;
  defaultType?: TransactionType;
  defaultAccountId?: string;
  defaultRelatedId?: string;
}) {
  const { accounts, categories } = useReferenceData();
  const editing = Boolean(transaction);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultsFor(transaction),
  });

  const transactionType = form.watch("transaction_type");
  const accountId = form.watch("account_id");
  const relatedId = form.watch("related_transaction_id");

  const refunds = useApi<Page<Transaction>>(
    open && transactionType === "refund"
      ? "/transactions?transaction_type=expense&page_size=100&sort_by=transaction_date&sort_dir=desc"
      : null
  );

  useEffect(() => {
    if (!open) return;
    form.reset({
      ...defaultsFor(transaction),
      transaction_type: transaction?.transaction_type ?? defaultType,
      related_transaction_id: transaction?.related_transaction_id ?? defaultRelatedId ?? "",
      account_id: transaction?.account_id ?? defaultAccountId ?? accounts[0]?.id ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, transaction?.id, defaultType, defaultAccountId, defaultRelatedId, accounts.length]);

  const activeAccounts = accounts.filter((account) => account.is_active);
  const incomeCategories = categoriesByType(categories, "income");
  const expenseCategories = categoriesByType(categories, "expense");
  const categoryType = transactionType === "income" ? "income" : "expense";
  const availableCategories = categoryType === "income" ? incomeCategories : expenseCategories;
  const selectedOriginal = refunds.data?.items.find((item) => item.id === relatedId);
  const remaining = selectedOriginal
    ? Math.max(
        toNumber(selectedOriginal.amount) -
          toNumber(selectedOriginal.refunded_amount) +
          (editing ? toNumber(transaction?.amount) : 0),
        0
      )
    : null;

  useEffect(() => {
    if (transactionType !== "refund" || !selectedOriginal) return;
    if (!form.getValues("account_id")) form.setValue("account_id", selectedOriginal.account_id);
    if (!form.getValues("description")) {
      form.setValue("description", `Refund: ${selectedOriginal.description}`);
    }
    if (remaining !== null && !form.getValues("amount")) {
      form.setValue("amount", remaining.toFixed(2));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOriginal?.id]);

  const submit = form.handleSubmit(async (values) => {
    const payload: Record<string, unknown> = {
      transaction_date: values.transaction_date,
      transaction_type: values.transaction_type,
      amount: values.amount,
      account_id: values.account_id,
      description: values.description,
      merchant_or_payee: values.merchant_or_payee || null,
      payment_method: values.payment_method || null,
      notes: values.notes || null,
      category_id:
        values.transaction_type === "income" || values.transaction_type === "expense"
          ? values.category_id
          : null,
      related_transaction_id:
        values.transaction_type === "refund" ? values.related_transaction_id : null,
    };

    try {
      if (editing && transaction) {
        await api(`/transactions/${transaction.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Transaction updated");
      } else {
        await api("/transactions", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Transaction recorded");
      }
      onOpenChange(false);
      onSaved?.();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });

  const isSubmitting = form.formState.isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit transaction" : "New transaction"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Changes are applied to the ledger and account balances immediately."
              : "Record income, spending, a refund or a balance adjustment."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Type" required htmlFor="txn-type">
              <NativeSelect
                id="txn-type"
                value={transactionType}
                onChange={(value) => {
                  form.setValue("transaction_type", value as TransactionType, {
                    shouldValidate: true,
                  });
                  if (value === "adjustment_increase" || value === "adjustment_decrease") {
                    form.setValue("category_id", "");
                    form.setValue("related_transaction_id", "");
                  }
                  if (value !== "refund") form.setValue("related_transaction_id", "");
                }}
                options={TXN_TYPES.map((type) => ({ value: type, label: TXN_LABELS[type] }))}
              />
            </Field>
            <Field label="Date" required htmlFor="txn-date">
              <Input id="txn-date" type="date" {...form.register("transaction_date")} />
            </Field>

            <Field label="Amount (PKR)" required htmlFor="txn-amount" error={form.formState.errors.amount?.message}>
              <Input
                id="txn-amount"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                placeholder="0.00"
                {...form.register("amount")}
              />
            </Field>
            <Field label="Account" required htmlFor="txn-account">
              <NativeSelect
                id="txn-account"
                value={accountId}
                onChange={(value) => form.setValue("account_id", value, { shouldValidate: true })}
                options={activeAccounts.map((account) => ({
                  value: account.id,
                  label: `${account.name} · ${formatMoney(account.current_balance, { decimals: false })}`,
                }))}
                placeholder="Choose account"
              />
            </Field>

            {transactionType === "income" || transactionType === "expense" ? (
              <Field
                label="Category"
                required
                htmlFor="txn-category"
                error={form.formState.errors.category_id?.message}
                className="sm:col-span-2"
              >
                <NativeSelect
                  id="txn-category"
                  value={form.watch("category_id") ?? ""}
                  onChange={(value) => form.setValue("category_id", value, { shouldValidate: true })}
                  options={availableCategories.map((category) => ({
                    value: category.id,
                    label: category.name,
                  }))}
                  placeholder="Choose category"
                />
              </Field>
            ) : null}

            {transactionType === "refund" ? (
              <Field
                label="Original expense"
                required
                htmlFor="txn-original"
                error={form.formState.errors.related_transaction_id?.message}
                hint={remaining !== null ? `${formatMoney(remaining)} still refundable` : "Pick the expense this refund belongs to"}
                className="sm:col-span-2"
              >
                <NativeSelect
                  id="txn-original"
                  value={relatedId ?? ""}
                  onChange={(value) => {
                    form.setValue("related_transaction_id", value, { shouldValidate: true });
                    form.setValue("amount", "");
                    form.setValue("description", "");
                  }}
                  options={(refunds.data?.items ?? []).map((item) => {
                    const left =
                      toNumber(item.amount) -
                      toNumber(item.refunded_amount) +
                      (editing ? toNumber(transaction?.amount) : 0);
                    return {
                      value: item.id,
                      label: `${item.transaction_date} · ${item.description} · ${formatMoney(item.amount)} (${formatMoney(left)} left)`,
                      disabled: left <= 0 && item.id !== relatedId,
                    };
                  })}
                  placeholder={refunds.loading ? "Loading expenses…" : "Choose original expense"}
                />
              </Field>
            ) : null}

            <Field
              label="Description"
              required
              htmlFor="txn-description"
              error={form.formState.errors.description?.message}
              className="sm:col-span-2"
            >
              <Input id="txn-description" placeholder="e.g. Weekly groceries" {...form.register("description")} />
            </Field>

            <Field label="Merchant / payee" htmlFor="txn-merchant">
              <Input id="txn-merchant" placeholder="Optional" {...form.register("merchant_or_payee")} />
            </Field>
            <Field label="Payment method" htmlFor="txn-method">
              <Input id="txn-method" placeholder="Cash, card, bank…" {...form.register("payment_method")} />
            </Field>

            <Field label="Notes" htmlFor="txn-notes" className="sm:col-span-2">
              <Textarea id="txn-notes" rows={2} placeholder="Optional context" {...form.register("notes")} />
            </Field>
          </div>

          {transactionType === "adjustment_increase" || transactionType === "adjustment_decrease" ? (
            <p className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-[11px] leading-5 text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-200">
              Adjustments change the account balance for reconciliation. They are never counted as
              income or spending in reports.
            </p>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
              {editing ? "Save changes" : "Record transaction"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
