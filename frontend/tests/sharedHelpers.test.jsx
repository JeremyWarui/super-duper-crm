import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { download } from "../src/api/client";
import ExportPanel from "../src/components/console/ExportPanel";
import { formatDay, initials } from "../src/lib/format";
import { eventDay } from "../src/pages/campaign/helpers";
import { workspaceInbox } from "../src/pages/campaign/shell";

vi.mock("../src/api/client", () => ({ download: vi.fn(() => Promise.resolve()) }));

afterEach(() => {
  vi.useRealTimers();
});

describe("shared helpers", () => {
  it("counts yesterday's event as past once it is past midnight in Nairobi", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-07T22:30:00Z"));
    const data = { events: [{ id: "e1", title: "Rally", status: "planned", scheduled_date: "2026-11-07" }] };

    expect(workspaceInbox(data, "manager").todo).toContainEqual(expect.objectContaining({ key: "unrecorded", text: "Record attendance: Rally" }));
  });

  it("badges only unread notices and narrows the to-do list to the picked ward", () => {
    const data = {
      notices: [{ id: "n1", text: "New", url: "/a", created_at: "2026-11-24T08:00:00Z", read_at: null }, { id: "n2", text: "Old", url: "/b", created_at: "2026-11-22T08:00:00Z", read_at: "2026-11-23T08:00:00Z" }],
      strategy: { units: [{ unit: "Ruai", ward: "w1", has_mobilizer: false }, { unit: "Njiru", ward: "w2", has_mobilizer: false }] },
      events: [],
    };

    const everywhere = workspaceInbox(data, "manager");
    const ruai = workspaceInbox(data, "manager", "w1");

    expect([everywhere.fresh.map((n) => n.text), everywhere.earlier.map((n) => n.text)]).toEqual([["New"], ["Old"]]);
    expect(everywhere.todo.map((n) => n.text)).toEqual(["2 wards have no mobilizer"]);
    expect(ruai.todo.map((n) => n.text)).toEqual(["Ruai has no mobilizer"]);
  });

  it("names the export after the Nairobi calendar day", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-07T22:30:00Z"));
    render(<ExportPanel />);

    fireEvent.click(screen.getByRole("button", { name: "Download export" }));

    expect(download).toHaveBeenCalledWith("/admin/export/", "export-2026-11-08.zip");
  });

  it("reads a day in Nairobi time, whatever the browser's zone", () => {
    expect(formatDay("2026-11-03")).toBe("3 November 2026");
    expect(formatDay("2026-11-02T22:30:00Z", { day: "numeric", month: "short" })).toBe("3 Nov");
  });

  it("calls an event today and gives its time by the Nairobi clock", () => {
    const now = new Date("2026-11-08T05:00:00Z");
    expect(eventDay({ scheduled_date: "2026-11-07T21:30:00Z" }, now)).toBe("Today · 00:30");
    expect(eventDay({ scheduled_date: "2026-11-09T00:00:00Z" }, now)).toBe("Mon 9 Nov");
  });

  it("takes initials only from words that start with a letter", () => {
    expect(initials("amina (Mama) Kariuki")).toBe("AK");
  });
});
