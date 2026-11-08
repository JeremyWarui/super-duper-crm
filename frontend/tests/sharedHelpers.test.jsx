import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { download } from "../src/api/client";
import ExportPanel from "../src/components/console/ExportPanel";
import { formatDay, initials } from "../src/lib/format";
import { eventDay } from "../src/pages/campaign/helpers";
import { workspaceAlerts } from "../src/pages/campaign/shell";

vi.mock("../src/api/client", () => ({ download: vi.fn(() => Promise.resolve()) }));

afterEach(() => {
  vi.useRealTimers();
});

describe("shared helpers", () => {
  it("counts yesterday's event as past once it is past midnight in Nairobi", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-07T22:30:00Z"));
    const data = { events: [{ id: "e1", title: "Rally", status: "planned", scheduled_date: "2026-11-07" }] };

    expect(workspaceAlerts(data, "manager")).toContainEqual(expect.objectContaining({ key: "unrecorded", text: "Record attendance: Rally" }));
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
