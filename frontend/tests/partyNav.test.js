/** The party CRM sidebar: each office sees only the pages it may open. */
import { describe, expect, it } from "vitest";
import { partyNav } from "../src/lib/partyNav";

const labels = (user) => partyNav(user).map((n) => n.label);

describe("the party CRM sidebar", () => {
  it("gives each office exactly its pages", () => {
    expect(labels({ party_roles: ["membership_officer"] })).toEqual(["Members", "Volunteers", "Data requests", "Branches"]);
    expect(labels({ party_roles: ["nominations_officer"] })).toEqual(["Aspirants", "Payments in"]);
    expect(labels({ party_roles: ["comms_officer"] })).toEqual(["Messages"]);
  });

  it("gives the superuser every page and the console", () => {
    expect(labels({ is_superuser: true, party_roles: [] })).toEqual([
      "Dashboard", "Members", "Volunteers", "Data requests", "Aspirants", "Payments in", "Messages", "Branches", "Website", "Console",
    ]);
  });
});
