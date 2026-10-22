"use client";

import { useMemo } from "react";
import { CalendarRange, ChevronDown } from "lucide-react";

import { NativeSelect } from "@/components/select-field";
import type { DateRange } from "@/lib/hooks";
import { monthEndISO, monthStartISO, toISODate } from "@/lib/format";
import { cn } from "@/lib/utils";

export function DateRangePicker({
  value,
  onChange,
  anchor = new Date(),
  className,
  compact = false,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
  anchor?: Date;
  className?: string;
  compact?: boolean;
}) {
  const presets = useMemo(() => {
    const anchorDate = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const prev = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
    const threeMonths = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 2, 1);
    const twelveMonths = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 11, 1);
    return [
      {
        value: "tracking",
        label: "Tracking month",
        range: { start: monthStartISO(anchorDate), end: monthEndISO(anchorDate) },
      },
      {
        value: "last-month",
        label: "Previous month",
        range: { start: monthStartISO(prev), end: monthEndISO(prev) },
      },
      {
        value: "last-3",
        label: "Last 3 months",
        range: { start: monthStartISO(threeMonths), end: monthEndISO(anchorDate) },
      },
      {
        value: "last-12",
        label: "Last 12 months",
        range: { start: monthStartISO(twelveMonths), end: monthEndISO(anchorDate) },
      },
      {
        value: "ytd",
        label: "Year to date",
        range: { start: toISODate(new Date(anchorDate.getFullYear(), 0, 1)), end: monthEndISO(anchorDate) },
      },
    ];
  }, [anchor]);

  const activePreset =
    presets.find((preset) => preset.range.start === value.start && preset.range.end === value.end)
      ?.value ?? "custom";

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <div className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-2 py-1 shadow-xs">
        <CalendarRange className="size-3.5 text-muted-foreground" />
        <div className="relative">
          <NativeSelect
            aria-label="Date range preset"
            value={activePreset}
            onChange={(next) => {
              const preset = presets.find((item) => item.value === next);
              if (preset) onChange(preset.range);
            }}
            options={[...presets.map(({ value: v, label }) => ({ value: v, label })), { value: "custom", label: "Custom range" }]}
            className="h-7 w-[160px] appearance-none border-0 bg-none bg-transparent py-0 pl-1 pr-7 shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
          <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        </div>
      </div>
      <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 shadow-xs">
        <input
          type="date"
          aria-label="Start date"
          value={value.start}
          max={value.end}
          onChange={(event) => {
            if (event.target.value) onChange({ ...value, start: event.target.value });
          }}
          className="h-7 rounded-md bg-transparent px-1.5 text-xs text-foreground outline-none focus-visible:bg-muted"
        />
        <span className="text-[11px] text-muted-foreground">→</span>
        <input
          type="date"
          aria-label="End date"
          value={value.end}
          min={value.start}
          onChange={(event) => {
            if (event.target.value) onChange({ ...value, end: event.target.value });
          }}
          className="h-7 rounded-md bg-transparent px-1.5 text-xs text-foreground outline-none focus-visible:bg-muted"
        />
      </div>
      {!compact ? (
        <span className="text-[11px] text-muted-foreground">
          {value.start} to {value.end}
        </span>
      ) : null}
    </div>
  );
}
