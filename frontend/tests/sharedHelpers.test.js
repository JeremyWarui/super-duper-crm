import { afterEach, describe, expect, it, vi } from "vitest";
import { initials } from "../src/lib/format";
import { workspaceAlerts } from "../src/pages/campaign/shell";

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

  it("takes initials only from words that start with a letter", () => {
    expect(initials("amina (Mama) Kariuki")).toBe("AK");
  });
});
