// Notifications: everything under the bell as a page, the phone's way in and a sidebar item.
import { Link } from "react-router-dom";
import { Bell, ChevronRight } from "lucide-react";
import { useReadAllNotices } from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { NoteBody } from "@/components/layout/TopBarTools";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useShellData, useWorkspaceArea, workspaceInbox } from "./shell";

export default function Notifications({ campaign, role }) {
  const data = useShellData(campaign, role);
  const { area } = useWorkspaceArea();
  const { fresh, earlier, todo } = workspaceInbox(data, role, area);
  const readAll = useReadAllNotices();
  const empty = !fresh.length && !earlier.length && !todo.length;
  return (
    <>
      <SlottedHeader
        context="Inbox"
        title="Notifications"
        sub="New notices, the work you have open, and what you have already read."
        actions={fresh.length ? <Button variant="outline" onClick={() => readAll.mutate()} loading={readAll.isPending}>Mark all as read</Button> : null}
      />
      {empty ? (
        <Card variant="outline" className="flex flex-col items-center gap-2 px-6 py-12 text-center">
          <Bell className="size-7 text-muted-foreground" aria-hidden />
          <p className="font-semibold">You are all caught up.</p>
          <p className="text-ui text-muted-foreground">{promiseOf(role)}</p>
        </Card>
      ) : (
        <div className="grid min-w-0 gap-4">
          <Section title="New" notes={fresh} none="Nothing new." />
          {todo.length > 0 && <Section title="To do" notes={todo} marker="bg-warn-foreground" />}
          {earlier.length > 0 && <Section title="Earlier" notes={earlier} dim />}
        </div>
      )}
    </>
  );
}

// What can reach this role under the bell, as the empty page says it.
function promiseOf(role) {
  const kinds = ["Announcements"];
  if (["coordinator", "mobilizer"].includes(role)) kinds.push("target changes");
  if (["candidate", "manager", "coordinator"].includes(role)) kinds.push("team sign-ups");
  if (["candidate", "manager"].includes(role)) kinds.push("payments to approve");
  const list = kinds.length === 1 ? kinds[0] : `${kinds.slice(0, -1).join(", ")} and ${kinds.at(-1)}`;
  return `${list} show up here.`;
}

function Section({ title, notes, none, dim = false, marker = "bg-primary" }) {
  return (
    <Card variant="outline" className="min-w-0 gap-0 p-0 sm:p-0" role="region" aria-label={title}>
      <h2 className="px-4 pt-3 pb-1 text-meta font-bold uppercase tracking-wide text-muted-foreground sm:px-5">{title}</h2>
      {notes.length === 0 ? (
        <p className="px-4 pb-4 text-ui text-muted-foreground sm:px-5">{none}</p>
      ) : (
        <ul className="m-0 flex list-none flex-col p-0">
          {notes.map((n) => (
            <li key={n.key} className="border-t border-line-soft">
              <Link to={n.to} className={cn("flex min-h-14 items-center gap-3 px-4 py-3 text-ink no-underline hover:bg-stone sm:px-5", dim && "opacity-70")}>
                <span aria-hidden className={cn("size-2.5 flex-none rounded-full", dim ? "bg-transparent" : marker)} />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5"><NoteBody note={n} /></span>
                <ChevronRight className="size-4 flex-none text-muted-foreground" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
