"use client";

import { useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CheckCircle2,
  FileSpreadsheet,
  FileUp,
  Loader2,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { DateRangePicker } from "@/components/date-range-picker";
import { Field, NativeSelect } from "@/components/select-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DefinitionNote,
  EmptyState,
  ErrorState,
  PageHeader,
  Pill,
  SectionHeading,
} from "@/components/ui-extras";
import { api, buildQuery, downloadCsv, errorMessage } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { useReferenceData, useTrackingPeriod } from "@/lib/hooks";
import type { ImportCommitResult, ImportPreview } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ImportExportPage() {
  const { range, setRange, anchor } = useTrackingPeriod();
  const { accounts } = useReferenceData();
  const fileInput = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportCommitResult | null>(null);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [createMissing, setCreateMissing] = useState(false);
  const [busy, setBusy] = useState<"preview" | "commit" | "sample" | "transactions" | "monthly" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportAccount, setExportAccount] = useState("");
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  const chooseFile = (next: File | null) => {
    setFile(next);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  const runPreview = async () => {
    if (!file) return;
    setBusy("preview");
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await api<ImportPreview>("/imports/preview", { method: "POST", body: formData });
      setPreview(data);
      toast.success(`${data.valid_rows} valid row${data.valid_rows === 1 ? "" : "s"} ready`);
    } catch (err) {
      setError(errorMessage(err));
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const runCommit = async () => {
    if (!file) return;
    setBusy("commit");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("skip_duplicates", String(skipDuplicates));
      formData.append("create_missing_categories", String(createMissing));
      const data = await api<ImportCommitResult>("/imports/commit", { method: "POST", body: formData });
      setResult(data);
      toast.success(`${data.created_count} transaction${data.created_count === 1 ? "" : "s"} imported`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const downloadSample = async () => {
    setBusy("sample");
    try {
      await downloadCsv("/imports/sample.csv", "transactions-template.csv");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const exportTransactions = async () => {
    if (!range) return;
    setBusy("transactions");
    try {
      await downloadCsv(
        `/exports/transactions.csv${buildQuery({
          start_date: range.start,
          end_date: range.end,
          account_id: exportAccount || undefined,
        })}`,
        "transactions-export.csv"
      );
      toast.success("Transactions export started");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const exportMonthly = async () => {
    setBusy("monthly");
    try {
      const [year, monthNumber] = month.split("-");
      await downloadCsv(
        `/exports/monthly-report.csv${buildQuery({ year, month: monthNumber })}`,
        `monthly-report-${month}.csv`
      );
      toast.success("Monthly report export started");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Data"
        title="Import & export"
        description="Bring existing history in as CSV with a validated preview, or export the ledger and monthly report for backup and analysis."
        actions={
          <Button variant="outline" onClick={downloadSample} disabled={busy === "sample"}>
            {busy === "sample" ? <Loader2 className="size-4 animate-spin" /> : <ArrowDownToLine className="size-4" />}
            Sample CSV
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-12">
        <section className="surface p-5 lg:col-span-7">
          <SectionHeading
            title="Import transactions"
            description="Upload a CSV, review every row, then commit only valid, non-duplicate rows."
            className="mb-4"
          />

          <div
            className={cn(
              "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/20 px-5 py-8 text-center transition-colors",
              file && "border-primary/40 bg-primary/[0.04]"
            )}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const dropped = event.dataTransfer.files?.[0];
              if (dropped) chooseFile(dropped);
            }}
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-secondary text-muted-foreground">
              <UploadCloud className="size-5" />
            </span>
            <p className="text-sm font-medium">{file ? file.name : "Drop a CSV here"}</p>
            <p className="text-[11px] text-muted-foreground">
              {file
                ? `${(file.size / 1024).toFixed(1)} KB · ready to preview`
                : "or choose a file from your computer. Dates must be YYYY-MM-DD."}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <input
                ref={fileInput}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
              />
              <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
                <FileUp className="size-3.5" /> Choose file
              </Button>
              {file ? (
                <Button variant="ghost" size="sm" onClick={() => chooseFile(null)}>
                  Clear
                </Button>
              ) : null}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={runPreview} disabled={!file || busy === "preview"}>
              {busy === "preview" ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}
              Preview rows
            </Button>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={skipDuplicates}
                onChange={(event) => setSkipDuplicates(event.target.checked)}
                className="size-3.5 accent-[var(--primary)]"
              />
              Skip duplicates
            </label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={createMissing}
                onChange={(event) => setCreateMissing(event.target.checked)}
                className="size-3.5 accent-[var(--primary)]"
              />
              Create missing categories
            </label>
          </div>

          {error ? <div className="mt-3"><ErrorState message={error} /></div> : null}

          {preview ? (
            <div className="mt-5 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Pill className="border-border bg-card">{preview.total_rows} rows</Pill>
                <Pill className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
                  {preview.valid_rows} valid
                </Pill>
                <Pill className="border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
                  {preview.duplicate_rows} duplicates
                </Pill>
                <Pill className="border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
                  {preview.invalid_rows} invalid
                </Pill>
              </div>

              <div className="max-h-[360px] overflow-auto rounded-lg border border-border">
                <table className="w-full min-w-[680px] text-left text-xs">
                  <thead className="sticky top-0 bg-muted/80 backdrop-blur">
                    <tr className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                      <th className="px-2.5 py-2 font-medium">Row</th>
                      <th className="px-2.5 py-2 font-medium">Date</th>
                      <th className="px-2.5 py-2 font-medium">Description</th>
                      <th className="px-2.5 py-2 font-medium">Type</th>
                      <th className="px-2.5 py-2 text-right font-medium">Amount</th>
                      <th className="px-2.5 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {preview.rows.map((row) => (
                      <tr key={row.row_number} className={cn(!row.is_valid && !row.is_duplicate && "bg-rose-50/40 dark:bg-rose-950/10")}>
                        <td className="px-2.5 py-1.5 text-muted-foreground">{row.row_number}</td>
                        <td className="whitespace-nowrap px-2.5 py-1.5">{row.normalized?.transaction_date ?? row.values.transaction_date ?? "—"}</td>
                        <td className="max-w-[200px] truncate px-2.5 py-1.5">{row.normalized?.description ?? row.values.description ?? "—"}</td>
                        <td className="px-2.5 py-1.5 text-muted-foreground">{row.normalized?.transaction_type ?? row.values.transaction_type ?? "—"}</td>
                        <td className="money px-2.5 py-1.5 text-right">
                          {row.normalized?.amount ? formatMoney(row.normalized.amount) : row.values.amount ?? "—"}
                        </td>
                        <td className="px-2.5 py-1.5">
                          {row.is_duplicate ? (
                            <span className="text-[10px] text-amber-700 dark:text-amber-400">Duplicate</span>
                          ) : row.is_valid ? (
                            <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700 dark:text-emerald-400">
                              <CheckCircle2 className="size-3" /> Ready
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] text-rose-700 dark:text-rose-400" title={row.errors.join("; ")}>
                              <XCircle className="size-3" /> {row.errors[0] ?? "Invalid"}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={runCommit} disabled={busy === "commit" || preview.valid_rows === 0}>
                  {busy === "commit" ? <Loader2 className="size-4 animate-spin" /> : <ArrowUpFromLine className="size-4" />}
                  Commit {preview.valid_rows} row{preview.valid_rows === 1 ? "" : "s"}
                </Button>
                <p className="text-[11px] text-muted-foreground">
                  Invalid rows are rejected individually; valid rows commit even if others fail.
                </p>
              </div>
            </div>
          ) : null}

          {result ? (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 dark:border-emerald-900 dark:bg-emerald-950/30">
              <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="size-4" /> Import complete
              </p>
              <p className="mt-1 text-[11px] leading-5 text-emerald-900/80 dark:text-emerald-200/80">
                {result.created_count} created · {result.skipped_count} skipped ·{" "}
                {result.rejected_count} rejected. Batch {result.import_batch_id.slice(0, 8)}.
              </p>
              {result.errors.length ? (
                <ul className="mt-2 space-y-1 text-[10px] text-rose-700 dark:text-rose-300">
                  {result.errors.slice(0, 5).map((item, index) => (
                    <li key={index}>{JSON.stringify(item)}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <DefinitionNote>
            Expected columns: <code>transaction_date</code>, <code>transaction_type</code>,{" "}
            <code>amount</code>, <code>account</code>, <code>category</code>, <code>description</code>{" "}
            and optional <code>merchant_or_payee</code>, <code>payment_method</code>,{" "}
            <code>notes</code>. Duplicate detection uses a content fingerprint, so re-uploading the
            same file does not double-post. Refunds need a matching original expense; import them as
            normal expenses first.
          </DefinitionNote>
        </section>

        <section className="space-y-4 lg:col-span-5">
          <div className="surface p-5">
            <SectionHeading title="Export transactions" description="Full ledger with transfers, as CSV" className="mb-3" />
            {range ? <DateRangePicker value={range} onChange={setRange} anchor={anchor} compact /> : null}
            <div className="mt-3">
              <Field label="Account" htmlFor="export-account">
                <NativeSelect
                  id="export-account"
                  value={exportAccount}
                  onChange={setExportAccount}
                  options={accounts.map((account) => ({ value: account.id, label: account.name }))}
                  placeholder="All accounts"
                />
              </Field>
            </div>
            <Button className="mt-3 w-full" variant="outline" onClick={exportTransactions} disabled={busy === "transactions"}>
              {busy === "transactions" ? <Loader2 className="size-4 animate-spin" /> : <ArrowDownToLine className="size-4" />}
              Download transactions CSV
            </Button>
          </div>

          <div className="surface p-5">
            <SectionHeading title="Export monthly report" description="Summary, accounts and categories for one month" className="mb-3" />
            <Field label="Month" htmlFor="export-month">
              <Input id="export-month" type="month" value={month} onChange={(event) => event.target.value && setMonth(event.target.value)} />
            </Field>
            <Button className="mt-3 w-full" variant="outline" onClick={exportMonthly} disabled={busy === "monthly"}>
              {busy === "monthly" ? <Loader2 className="size-4 animate-spin" /> : <ArrowDownToLine className="size-4" />}
              Download report CSV
            </Button>
          </div>

          <div className="surface p-5">
            <SectionHeading title="Backup guidance" className="mb-2" />
            <ul className="space-y-2 text-[11px] leading-5 text-muted-foreground">
              <li>Export the full ledger CSV before bulk edits or a database migration.</li>
              <li>For a complete backup, use <code>pg_dump</code> against the PostgreSQL database.</li>
              <li>Keep the baseline snapshot intact; historical usage is reported separately and never mixed into monthly spending.</li>
              <li>Exports respect the active filters and exclude soft-deleted entries.</li>
            </ul>
          </div>
        </section>
      </div>

      {!preview && !result ? (
        <EmptyState
          icon={ArrowDownToLine}
          title="Nothing staged yet"
          description="Download the sample CSV to see the exact column format, then drag your bank export into the drop zone."
        />
      ) : null}
    </div>
  );
}
