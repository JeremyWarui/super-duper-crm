/**
 * The test doubles still match the shape the backend promises.
 *
 * Read from `contracts/frontend-api.json`, the same file
 * `backend/evals/test_frontend_contract.py` checks the API against. Without
 * this, a backend field rename would leave every test here green against a
 * fixture that no longer resembles the real response.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CAMPAIGN,
  EVENTS,
  STRATEGY,
  TARGETS,
  dashboardRoutes,
} from "./helpers";

// vitest runs from the frontend directory; the contract sits beside it.
const CONTRACT = JSON.parse(
  readFileSync(resolve(process.cwd(), "../contracts/frontend-api.json"), "utf8"),
);

function fieldsFor(route) {
  return CONTRACT.reads[route];
}

function expectHasAll(object, fields, what) {
  const missing = fields.filter((name) => !(name in object));
  expect(missing, `${what} is missing ${missing}`).toEqual([]);
}

describe("the fixtures against the contract", () => {
  it("a campaign carries what the dashboard reads", () => {
    expectHasAll(CAMPAIGN, fieldsFor("GET /api/campaigns/"), "the campaign fixture");
  });

  it("a target carries what the targets table reads", () => {
    expectHasAll(TARGETS[0], fieldsFor("GET /api/targets/"), "the target fixture");
  });

  it("an event carries what the events table reads", () => {
    expectHasAll(EVENTS[0], fieldsFor("GET /api/events/"), "the event fixture");
  });

  it("the strategy carries what the overview reads", () => {
    expectHasAll(STRATEGY, fieldsFor("GET /api/strategy/"), "the strategy fixture");
  });

  it("a strategy unit carries what the targeting table reads", () => {
    expectHasAll(
      STRATEGY.units[0],
      CONTRACT.nested_reads["GET /api/strategy/.units"],
      "a strategy unit",
    );
  });

  it("a strategy note carries what the panel reads", () => {
    expectHasAll(
      STRATEGY.notes[0],
      CONTRACT.nested_reads["GET /api/strategy/.notes"],
      "a strategy note",
    );
  });

  it("stubs every route the dashboard loads", () => {
    const stubbed = Object.keys(dashboardRoutes()).map((key) => {
      const [method, path] = key.split(" ");
      return `${method} /api${path}`;
    });
    for (const route of ["GET /api/campaigns/", "GET /api/strategy/", "GET /api/targets/"]) {
      expect(stubbed).toContain(route);
    }
  });
});

describe("the choice strings the app switches on", () => {
  it("matches the roles the nav is keyed by", async () => {
    const { default: App } = await import("../src/App");
    expect(App).toBeTypeOf("function");
    expect(CONTRACT.enums["user.role"].sort()).toEqual(
      ["candidate", "manager", "mobilizer"].sort(),
    );
  });

  it("matches the event status the list checks for", () => {
    expect(CONTRACT.enums["event.status"]).toContain("done");
    expect(CONTRACT.enums["event.status"]).toContain("planned");
  });

  it("matches the support levels the filter offers", () => {
    expect(CONTRACT.enums["supporter.support_level"].sort()).toEqual(
      ["opposed", "supporter", "undecided"].sort(),
    );
  });

  it("uses the fixture values the contract allows", () => {
    expect(CONTRACT.enums["event.status"]).toContain(EVENTS[0].status);
    expect(CONTRACT.enums["campaign.office_level"]).toContain(CAMPAIGN.office_level);
  });
});

describe("the source against the contract", () => {
  const read = (path) => readFileSync(resolve(process.cwd(), "src", path), "utf8");

  it("sends the token under the scheme the contract names", () => {
    expect(read("api/client.js")).toContain("Token ${token}");
  });

  it("reads the error field the backend fills in", () => {
    /* The client shows `detail`; anything else renders as [object Object]. */
    expect(CONTRACT.error_shape.detail).toBe("string");
    expect(read("api/client.js")).toContain("data?.detail");
  });

  it("calls every route it contracts for", () => {
    const source = read("api/hooks.js") + read("store/auth.js");
    for (const route of Object.keys(CONTRACT.reads)) {
      const path = route.split(" ")[1].replace("/api", "");
      expect(source, `nothing calls ${path}`).toContain(path.replace(/\/$/, "/"));
    }
  });

  it("names the centre field the API returns, not the prototype's", () => {
    /* A ward race targets registration centres now, not polling stations. */
    const source = read("App.jsx");
    expect(source).toContain("centre_name");
    expect(source).not.toContain("station_name");
  });
});
