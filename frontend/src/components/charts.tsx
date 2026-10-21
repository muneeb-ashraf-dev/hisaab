"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import { formatCompact, formatMoney } from "@/lib/format";
import type { CategorySlice, MonthlyPoint, TrendPoint } from "@/lib/types";

const axisStyle = {
  fontSize: 10,
  fill: "var(--muted-foreground)",
} as const;

const tooltipStyle = {
  borderRadius: 10,
  border: "1px solid var(--border)",
  background: "var(--popover)",
  color: "var(--popover-foreground)",
  fontSize: 12,
  boxShadow: "0 12px 32px -18px rgba(20,40,34,0.4)",
  padding: "8px 10px",
} as const;

type TooltipPayloadItem = {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
};

function MoneyTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={tooltipStyle}>
      <p className="mb-1 text-[11px] font-medium text-muted-foreground">{label}</p>
      <div className="space-y-0.5">
        {payload.map((item) => (
          <div key={String(item.dataKey)} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5">
              <span className="size-1.5 rounded-full" style={{ background: item.color }} />
              {item.name}
            </span>
            <span className="money font-medium">{formatMoney(Number(item.value ?? 0))}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CashflowChart({ data, height = 260 }: { data: TrendPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={axisStyle}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={24}
        />
        <YAxis
          tick={axisStyle}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value) => formatCompact(value)}
          width={52}
        />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
        <Bar dataKey="income" name="Income" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} maxBarSize={22} />
        <Bar
          dataKey="net_expenses"
          name="Net expenses"
          fill={CHART_COLORS[3]}
          radius={[3, 3, 0, 0]}
          maxBarSize={22}
        />
        <Line
          type="monotone"
          dataKey="net_cash_flow"
          name="Net cash flow"
          stroke={CHART_COLORS[2]}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function CategoryDonut({
  data,
  height = 220,
}: {
  data: CategorySlice[];
  height?: number;
}) {
  const slices = data.slice(0, 7);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={slices}
          dataKey="amount"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={58}
          outerRadius={84}
          paddingAngle={2}
          stroke="var(--card)"
          strokeWidth={2}
        >
          {slices.map((slice, index) => (
            <Cell key={slice.category_id ?? slice.name} fill={slice.color || CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<MoneyTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function MonthlySeriesChart({
  data,
  height = 300,
  showBalance = true,
}: {
  data: MonthlyPoint[];
  height?: number;
  showBalance?: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} axisLine={false} tickLine={false} minTickGap={16} />
        <YAxis
          tick={axisStyle}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value) => formatCompact(value)}
          width={52}
        />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
        <Bar dataKey="income" name="Income" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} maxBarSize={26} />
        <Bar dataKey="net_expenses" name="Net expenses" fill={CHART_COLORS[3]} radius={[3, 3, 0, 0]} maxBarSize={26} />
        {showBalance ? (
          <Line
            type="monotone"
            dataKey="closing_balance"
            name="Closing balance"
            stroke={CHART_COLORS[2]}
            strokeWidth={2}
            dot={false}
          />
        ) : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function TrendAreaChart({
  data,
  dataKey = "net_expenses",
  height = 220,
}: {
  data: MonthlyPoint[];
  dataKey?: "net_expenses" | "income" | "closing_balance";
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
        <defs>
          <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS[0]} stopOpacity={0.28} />
            <stop offset="100%" stopColor={CHART_COLORS[0]} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} axisLine={false} tickLine={false} minTickGap={16} />
        <YAxis
          tick={axisStyle}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value) => formatCompact(value)}
          width={52}
        />
        <Tooltip content={<MoneyTooltip />} />
        <Area
          type="monotone"
          dataKey={dataKey}
          name="Net expenses"
          stroke={CHART_COLORS[0]}
          strokeWidth={2}
          fill="url(#trend-fill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CategoryBars({ data }: { data: Array<{ name: string; amount: string; color: string }> }) {
  const chartData = data.map((item) => ({ name: item.name, amount: Number(item.amount), color: item.color }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, chartData.length * 34)}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" tick={axisStyle} axisLine={false} tickLine={false} tickFormatter={(value) => formatCompact(value)} />
        <YAxis type="category" dataKey="name" tick={{ ...axisStyle, fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
        <Bar dataKey="amount" name="Net spend" radius={[0, 4, 4, 0]} maxBarSize={16}>
          {chartData.map((item, index) => (
            <Cell key={item.name} fill={item.color || CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
