/** Every header shows the party from the website settings, never a product name. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the party's branding", () => {
  it("names the party from its settings on the sign-in page and in the tab title", async () => {
    stubApi({ "GET /party/": { name: "Pamoja Party", logo_url: "" } });
    renderApp(<Login />);

    expect(await screen.findByText("Pamoja Party")).toBeInTheDocument();
    expect(document.title).toBe("Pamoja Party");
  });

  it("is not hard-coded anywhere in the source", () => {
    const root = resolve(process.cwd(), "src");
    const naming = globSync("**/*.{js,jsx,css}", { cwd: root }).filter((path) =>
      /mzigo/i.test(readFileSync(resolve(root, path), "utf8")),
    );

    expect(naming).toEqual([]);
  });
});
