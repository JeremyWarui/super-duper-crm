/** The party CRM sidebar: each office sees only the pages it may open. */
import { describe, expect, it } from "vitest";
import { partyNav } from "../src/pages/party/Portal";

const labels = (user) => partyNav(user).map((n) => n.label);

describe("the party CRM sidebar", () => {
  it("gives each office exactly its pages", () => {
    expect(labels({ party_roles: ["membership_officer"] })).toEqual(["Members", "Volunteers"]);
    expect(labels({ party_roles: ["nominations_officer"] })).toEqual(["Aspirants"]);
    expect(labels({ party_roles: ["finance_officer"] })).toEqual(["Finance"]);
  });

  it("gives the superuser every page and the console", () => {
    expect(labels({ is_superuser: true, party_roles: [] })).toEqual([
      "Dashboard", "Members", "Volunteers", "Aspirants", "Finance", "Website", "Console",
    ]);
  });
});
