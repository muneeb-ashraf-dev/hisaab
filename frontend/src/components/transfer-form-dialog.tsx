"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight, Loader2 } from "lucide-react";
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
import { formatMoney } from "@/lib/format";
import { useReferenceData } from "@/lib/hooks";
import type { Transfer } from "@/lib/types";

const schema = z
  .object({
    transfer_date: z.string().min(1, "Choose a date"),
    from_account_id: z.string().min(1, "Choose the source account"),
    to_account_id: z.string().min(1, "Choose the destination account"),
    amount: z
      .string()
      .min(1, "Enter an amount")
      .refine((value) => Number(value) > 0, "Amount must be greater than zero"),
    description: z.string().trim().min(1, "Add a short description").max(255),
    notes: z.string().optional(),
  })
  .refine((values) => values.from_account_id !== values.to_account_id, {
    path: ["to_account_id"],
    message: "Source and destination must be different accounts",
  });

type FormValues = z.infer<typeof schema>;

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function TransferFormDialog({
  open,
  onOpenChange,
  transfer,
  onSaved,
  defaultFromId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transfer?: Transfer | null;
  onSaved?: () => void;
  defaultFromId?: string;
}) {
  const { accounts } = useReferenceData();
  const editing = Boolean(transfer);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      transfer_date: todayISO(),
      from_account_id: "",
      to_account_id: "",
      amount: "",
      description: "",
      notes: "",
    },
  });

  const fromId = form.watch("from_account_id");

  useEffect(() => {
    if (!open) return;
    const active = accounts.filter((account) => account.is_active);
    form.reset({
      transfer_date: transfer?.transfer_date ?? todayISO(),
      from_account_id: transfer?.from_account_id ?? defaultFromId ?? active[0]?.id ?? "",
      to_account_id: transfer?.to_account_id ?? active.find((a) => a.id !== (defaultFromId ?? active[0]?.id))?.id ?? "",
      amount: transfer?.amount ?? "",
      description: transfer?.description ?? "",
      notes: transfer?.notes ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, transfer?.id, defaultFromId, accounts.length]);

  const submit = form.handleSubmit(async (values) => {
    const payload = {
      transfer_date: values.transfer_date,
      from_account_id: values.from_account_id,
      to_account_id: values.to_account_id,
      amount: values.amount,
      description: values.description,
      notes: values.notes || null,
    };
    try {
      if (editing && transfer) {
        await api(`/transfers/${transfer.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Transfer updated");
      } else {
        await api("/transfers", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Transfer moved between accounts");
      }
      onOpenChange(false);
      onSaved?.();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });

  const active = accounts.filter((account) => account.is_active);
  const destination = active.find((account) => account.id === fromId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit transfer" : "New transfer"}</DialogTitle>
          <DialogDescription>
            Transfers move money between your own accounts. They never count as income or
            expenses.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Date" required htmlFor="trf-date">
              <Input id="trf-date" type="date" {...form.register("transfer_date")} />
            </Field>
            <Field label="Amount (PKR)" required htmlFor="trf-amount" error={form.formState.errors.amount?.message}>
              <Input
                id="trf-amount"
                type="number"
                step="0.01"
                min="0"
                inputMode="decimal"
                placeholder="0.00"
                {...form.register("amount")}
              />
            </Field>

            <Field label="From" required htmlFor="trf-from">
              <NativeSelect
                id="trf-from"
                value={form.watch("from_account_id")}
                onChange={(value) => form.setValue("from_account_id", value, { shouldValidate: true })}
                options={active.map((account) => ({
                  value: account.id,
                  label: `${account.name} · ${formatMoney(account.current_balance, { decimals: false })}`,
                }))}
                placeholder="Choose account"
              />
            </Field>
            <Field
              label="To"
              required
              htmlFor="trf-to"
              error={form.formState.errors.to_account_id?.message}
              hint={destination ? `Available: ${formatMoney(destination.current_balance)}` : undefined}
            >
              <NativeSelect
                id="trf-to"
                value={form.watch("to_account_id")}
                onChange={(value) => form.setValue("to_account_id", value, { shouldValidate: true })}
                options={active.map((account) => ({
                  value: account.id,
                  label: account.name,
                  disabled: account.id === fromId,
                }))}
                placeholder="Choose account"
              />
            </Field>

            <Field
              label="Description"
              required
              htmlFor="trf-description"
              error={form.formState.errors.description?.message}
              className="sm:col-span-2"
            >
              <Input id="trf-description" placeholder="e.g. Month-end savings move" {...form.register("description")} />
            </Field>
            <Field label="Notes" htmlFor="trf-notes" className="sm:col-span-2">
              <Textarea id="trf-notes" rows={2} placeholder="Optional context" {...form.register("notes")} />
            </Field>
          </div>

          {fromId && form.watch("to_account_id") ? (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {active.find((a) => a.id === fromId)?.name}
              </span>
              <ArrowRight className="size-3.5" />
              <span className="font-medium text-foreground">
                {active.find((a) => a.id === form.watch("to_account_id"))?.name}
              </span>
              <span className="ml-auto">Total balance stays unchanged</span>
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
              {editing ? "Save changes" : "Move money"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
