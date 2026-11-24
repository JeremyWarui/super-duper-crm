import type * as React from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

/** The phone tab bar for field roles: their own pages, one tap from anywhere; `badge` counts what is new on a tab. */
export default function FieldTabs({ items }: { items: { to: string; label: string; badge?: number; icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" }> }[] }) {
  return (
    <>
      <div aria-hidden="true" className="h-[76px] flex-none" />
      <nav aria-label="Field tabs" className="fixed inset-x-0 bottom-0 z-30 grid border-t border-line bg-white px-1 pt-1.5 pb-[max(10px,env(safe-area-inset-bottom))]" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map(({ to, label, badge, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => cn("flex min-h-[52px] min-w-0 flex-col items-center justify-center gap-1 px-1 text-center text-meta leading-tight break-words hyphens-auto no-underline", isActive ? "font-bold text-primary" : "font-semibold text-muted-foreground")}>
            <span className="relative">
              {Icon && <Icon aria-hidden="true" className="size-[22px]" />}
              {badge ? <span className="absolute -top-1.5 -right-2.5 min-w-[18px] rounded-full bg-destructive px-1 text-center text-[11px] font-bold leading-[18px] text-white"><span className="sr-only">, </span>{badge > 99 ? "99+" : badge}<span className="sr-only"> new</span></span> : null}
            </span>
            {label.replace("Announcements", "Announce­ments")}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
