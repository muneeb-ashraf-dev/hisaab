import { format, parseISO, isValid } from "date-fns";

/** Pakistani numbering uses 2,2,3 grouping (lakh / crore). */
export function groupPKR(integer: string): string {
  const digits = integer.replace(/\D/g, "");
  if (digits.length <= 3) return digits;
  const last3 = digits.slice(-3);
  const rest = digits.slice(0, -3);
  const pairs: string[] = [];
  let cursor = rest;
  while (cursor.length > 2) {
    pairs.unshift(cursor.slice(-2));
    cursor = cursor.slice(0, -2);
  }
  if (cursor) pairs.unshift(cursor);
  return [...pairs, last3].join(",");
}

export function formatMoney(
  value: string | number | null | undefined,
  options: { decimals?: boolean; sign?: boolean; currency?: boolean } = {}
): string {
  const { decimals = true, sign = false, currency = true } = options;
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) return currency ? "Rs 0" : "0";
  const negative = numeric < 0;
  const absolute = Math.abs(numeric);
  const fixed = decimals ? absolute.toFixed(2) : Math.round(absolute).toString();
  const [whole, fraction] = fixed.split(".");
  const prefix = negative ? "−" : sign && numeric > 0 ? "+" : "";
  const grouped = groupPKR(whole);
  const body = fraction ? `${grouped}.${fraction}` : grouped;
  return `${prefix}${currency ? "Rs " : ""}${body}`;
}

/** Compact labels for chart axes: 1.2L, 45k, 1.1Cr. */
export function formatCompact(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0);
  const absolute = Math.abs(numeric);
  const sign = numeric < 0 ? "−" : "";
  if (absolute >= 10_000_000) return `${sign}${(absolute / 10_000_000).toFixed(1)}Cr`;
  if (absolute >= 100_000) return `${sign}${(absolute / 100_000).toFixed(1)}L`;
  if (absolute >= 1_000) return `${sign}${(absolute / 1_000).toFixed(0)}k`;
  return `${sign}${Math.round(absolute)}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "0 KB";
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function toNumber(value: string | number | null | undefined): number {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

export function parseDateValue(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const parsed = typeof value === "string" ? parseISO(value) : value;
  return isValid(parsed) ? parsed : null;
}

export function formatDate(value: string | Date | null | undefined, pattern = "d MMM yyyy"): string {
  const parsed = parseDateValue(value);
  return parsed ? format(parsed, pattern) : "—";
}

export function formatDateShort(value: string | Date | null | undefined): string {
  return formatDate(value, "d MMM");
}

export function formatDateTime(value: string | Date | null | undefined): string {
  return formatDate(value, "d MMM yyyy, h:mm a");
}

export function toISODate(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function monthStartISO(date = new Date()): string {
  return format(new Date(date.getFullYear(), date.getMonth(), 1), "yyyy-MM-dd");
}

export function monthEndISO(date = new Date()): string {
  return format(new Date(date.getFullYear(), date.getMonth() + 1, 0), "yyyy-MM-dd");
}

export function addMonthsISO(iso: string, delta: number): string {
  const parsed = parseISO(iso);
  return toISODate(new Date(parsed.getFullYear(), parsed.getMonth() + delta, 1));
}

export function monthLabel(iso: string): string {
  return formatDate(iso, "MMMM yyyy");
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function initials(name: string): string {
  return name
    .split(/[\s-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
