// Notifications: everything under the bell as a page, the phone's way in and a sidebar item.
import { Link } from "react-router-dom";
import { Bell, ChevronRight } from "lucide-react";
import { useReadNotice } from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useShellData, workspaceAlerts } from "./shell";

export default function Notifications({ campaign, role }) {
  const data = useShellData(campaign, role);
  const items = workspaceAlerts(data, role);
  const read = useReadNotice();
  const notices = data.notices || [];
  const clearAll = () => notices.forEach((n) => read.mutate(n.id));
  return (
    <>
      <SlottedHeader
        context="Inbox"
        title="Notifications"
        sub="What needs you now. Opening one takes you to its page."
        actions={notices.length ? <Button variant="outline" onClick={clearAll} loading={read.isPending}>Mark all as read</Button> : null}
      />
      <Card variant="outline" className="min-w-0 gap-0 p-0 sm:p-0">
        {items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <Bell className="size-7 text-muted-foreground" aria-hidden />
            <p className="font-semibold">You are all caught up.</p>
            <p className="text-ui text-muted-foreground">New announcements, target changes and work that needs you show up here.</p>
          </div>
        ) : (
          <ul className="m-0 flex list-none flex-col p-0">
            {items.map((n) => (
              <li key={n.key} className="border-b border-line-soft last:border-b-0">
                <Link to={n.to} className="flex min-h-14 items-center gap-3 px-4 py-3 text-ink no-underline hover:bg-stone sm:px-5">
                  <span aria-hidden className="size-2.5 flex-none rounded-full bg-primary" />
                  <span className="min-w-0 flex-1 text-body font-semibold">{n.text}</span>
                  <ChevronRight className="size-4 flex-none text-muted-foreground" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
