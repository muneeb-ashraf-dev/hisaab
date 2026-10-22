"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowDownUp,
  ArrowLeftRight,
  CalendarClock,
  ChartColumn,
  CircleDot,
  HandCoins,
  LayoutDashboard,
  Menu,
  Repeat2,
  Settings2,
  Target,
  Trophy,
  WalletCards,
} from "lucide-react";

import { BackupReminder } from "@/components/backup-reminder";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { NAV_ITEMS } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { useSystemStatus } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const ICONS = {
  LayoutDashboard,
  ArrowLeftRight,
  Repeat2,
  ChartColumn,
  Target,
  Trophy,
  CalendarClock,
  HandCoins,
  ArrowDownUp,
  Settings2,
} as const;

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="flex size-9 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-sm">
        <WalletCards className="size-[18px]" strokeWidth={1.9} />
      </span>
      <span className={cn("leading-none", compact && "sr-only")}>
        <span className="block font-heading text-[17px] font-semibold tracking-tight text-sidebar-foreground">
          Hisaab
        </span>
        <span className="mt-1 block text-[10px] uppercase tracking-[0.22em] text-sidebar-foreground/55">
          Personal ledger
        </span>
      </span>
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const groups = Array.from(new Set(NAV_ITEMS.map((item) => item.group)));

  return (
    <nav className="space-y-6">
      {groups.map((group) => (
        <div key={group}>
          <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-sidebar-foreground/40">
            {group}
          </p>
          <ul className="space-y-1">
            {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
              const Icon = ICONS[item.icon];
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                    )}
                  >
                    <Icon
                      className={cn(
                        "size-[17px] transition-colors",
                        active ? "text-sidebar-primary" : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/80"
                      )}
                      strokeWidth={1.9}
                    />
                    <span>{item.label}</span>
                    {active ? (
                      <span className="ml-auto size-1.5 rounded-full bg-sidebar-primary" />
                    ) : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter() {
  const { data, error } = useSystemStatus();
  return (
    <div className="rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 p-3">
      <div className="flex items-center gap-2 text-[11px] text-sidebar-foreground/60">
        <CircleDot
          className={cn(
            "size-3",
            data?.database_connected ? "text-emerald-400" : error ? "text-rose-400" : "text-amber-300"
          )}
        />
        {data?.database_connected ? "Database connected" : error ? "API unreachable" : "Connecting…"}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <span className="text-[10px] uppercase tracking-[0.16em] text-sidebar-foreground/40">
          Baseline
        </span>
        <span className="text-[11px] font-medium text-sidebar-foreground/80">
          {data?.baseline_date ? formatDate(data.baseline_date, "d MMM yyyy") : "—"}
        </span>
      </div>
    </div>
  );
}

function DesktopSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col bg-sidebar px-4 py-5 lg:flex">
      <div className="px-2">
        <Brand />
      </div>
      <div className="mt-8 flex-1 overflow-y-auto scrollbar-thin pr-1">
        <NavLinks />
      </div>
      <div className="mt-4">
        <SidebarFooter />
      </div>
    </aside>
  );
}

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { data } = useSystemStatus();
  return (
    <div className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border/70 bg-background/85 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <Menu className="size-5" />
        </Button>
        <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
          <span className="font-medium text-foreground">Hisaab</span>
          <span className="text-border">/</span>
          <span>Single-user workspace</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground sm:inline-flex">
          {data?.currency ?? "PKR"}
        </span>
        <span className="hidden text-xs text-muted-foreground md:inline">
          {formatDate(new Date(), "EEEE, d MMM")}
        </span>
        <span className="flex size-8 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
          A
        </span>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <DesktopSidebar />
      <div className="lg:pl-[248px]">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <BackupReminder />
        <main className="mx-auto w-full max-w-[1420px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="page-enter">{children}</div>
        </main>
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-[280px] border-0 bg-sidebar p-0 text-sidebar-foreground">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-full flex-col px-4 py-5">
            <div className="px-2">
              <Brand />
            </div>
            <div className="mt-8 flex-1 overflow-y-auto scrollbar-thin pr-1">
              <NavLinks onNavigate={() => setMobileOpen(false)} />
            </div>
            <div className="mt-4">
              <SidebarFooter />
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
