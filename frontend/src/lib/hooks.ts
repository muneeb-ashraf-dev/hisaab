"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseISO } from "date-fns";

import { api, errorMessage } from "@/lib/api";
import { monthEndISO, monthStartISO, toISODate } from "@/lib/format";
import type {
  AccountWithBalance,
  BackupResult,
  BackupStatus,
  Category,
  SystemStatus,
} from "@/lib/types";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  setData: (value: T) => void;
}

export function useApi<T>(path: string | null): AsyncState<T> {
  const [state, setState] = useState<{
    key: string | null;
    data: T | null;
    error: string | null;
  }>({ key: null, data: null, error: null });
  const [tick, setTick] = useState(0);
  const requestId = useRef(0);
  const requestKey = path ? `${path}::${tick}` : null;

  useEffect(() => {
    if (!path || !requestKey) return;
    const current = ++requestId.current;
    const controller = new AbortController();

    api<T>(path, { signal: controller.signal })
      .then((value) => {
        if (current === requestId.current) {
          setState({ key: requestKey, data: value, error: null });
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || current !== requestId.current) return;
        setState((previous) => ({
          key: requestKey,
          data: previous.data,
          error: errorMessage(err),
        }));
      });

    return () => {
      controller.abort();
    };
  }, [path, requestKey]);

  const refresh = useCallback(() => setTick((value) => value + 1), []);
  const update = useCallback((value: T) => {
    setState((previous) => ({ ...previous, data: value }));
  }, []);

  // Loading, data and errors are derived from the key of the latest request
  // rather than set synchronously inside the effect.
  return {
    data: state.data,
    loading: Boolean(path) && state.key !== requestKey,
    error: state.key === requestKey ? state.error : null,
    refresh,
    setData: update,
  };
}

export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useReferenceData(): {
  accounts: AccountWithBalance[];
  categories: Category[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const accounts = useApi<AccountWithBalance[]>("/accounts");
  const categories = useApi<Category[]>("/categories");

  const refreshAccounts = accounts.refresh;
  const refreshCategories = categories.refresh;

  const refresh = useCallback(() => {
    refreshAccounts();
    refreshCategories();
  }, [refreshAccounts, refreshCategories]);

  return {
    accounts: accounts.data ?? [],
    categories: categories.data ?? [],
    loading: accounts.loading || categories.loading,
    error: accounts.error ?? categories.error,
    refresh,
  };
}

export function useSystemStatus(): AsyncState<SystemStatus> {
  return useApi<SystemStatus>("/system/status");
}

export interface BackupStatusState extends AsyncState<BackupStatus> {
  backingUp: boolean;
  backupNow: () => Promise<BackupResult>;
}

/** Polls the local-backup status and exposes the manual backup action. */
export function useBackupStatus({ pollMs = 30000 }: { pollMs?: number } = {}): BackupStatusState {
  const state = useApi<BackupStatus>("/system/backup/status");
  const { refresh } = state;
  const [backingUp, setBackingUp] = useState(false);

  const backupNow = useCallback(async () => {
    setBackingUp(true);
    try {
      const result = await api<BackupResult>("/system/backup", { method: "POST" });
      refresh();
      return result;
    } finally {
      setBackingUp(false);
    }
  }, [refresh]);

  useEffect(() => {
    const onDataChanged = () => refresh();
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("hisaab:data-changed", onDataChanged);
    document.addEventListener("visibilitychange", onVisibility);

    let timer: ReturnType<typeof setInterval> | undefined;
    if (pollMs > 0) {
      timer = setInterval(refresh, pollMs);
    }

    return () => {
      window.removeEventListener("hisaab:data-changed", onDataChanged);
      document.removeEventListener("visibilitychange", onVisibility);
      if (timer) clearInterval(timer);
    };
  }, [pollMs, refresh]);

  return { ...state, backingUp, backupNow };
}

export interface DateRange {
  start: string;
  end: string;
}

/** The reporting data starts at the baseline date. When the baseline is in the
 * future (fresh setup), the UI should open on that period rather than an empty
 * current month. */
export function trackingAnchor(baselineDate?: string | null): Date {
  const now = new Date();
  if (!baselineDate) return now;
  const baseline = parseISO(baselineDate);
  if (Number.isNaN(baseline.getTime())) return now;
  return baseline > now ? baseline : now;
}

export function useTrackingPeriod(): {
  range: DateRange | null;
  setRange: (range: DateRange) => void;
  status: AsyncState<SystemStatus>;
  anchor: Date;
  reset: () => void;
} {
  const status = useSystemStatus();
  const [range, setRangeState] = useState<DateRange | null>(null);

  // Until the user picks a range, derive the default from the baseline-aware
  // anchor. Keeping this out of an effect avoids a cascading render when the
  // system status request resolves.
  const defaultRange = useMemo<DateRange | null>(() => {
    if (!status.data && !status.error) return null;
    const anchor = trackingAnchor(status.data?.baseline_date);
    return { start: monthStartISO(anchor), end: monthEndISO(anchor) };
  }, [status.data, status.error]);

  const reset = useCallback(() => setRangeState(null), []);

  return {
    range: range ?? defaultRange,
    setRange: setRangeState,
    status,
    anchor: trackingAnchor(status.data?.baseline_date),
    reset,
  };
}

export function currentYearAnchor(baselineDate?: string | null): number {
  return trackingAnchor(baselineDate).getFullYear();
}

export function todayISO(): string {
  return toISODate(new Date());
}

export function activeAccounts(accounts: AccountWithBalance[]): AccountWithBalance[] {
  return accounts.filter((account) => account.is_active);
}

export function categoriesByType(categories: Category[], type: "income" | "expense"): Category[] {
  return categories
    .filter((category) => category.category_type === type && category.is_active)
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
}
