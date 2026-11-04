/** Every header shows the party from the website settings, never a product name. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { BrandingProvider } from "@/theme/branding";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the party's branding", () => {
  it("names the party from its settings on the sign-in page and in the tab title", async () => {
    stubApi({ "GET /site/": { name: "Pamoja Party", logo_url: "" } });
    renderApp(<Login />);

    expect(await screen.findByText("Pamoja Party")).toBeInTheDocument();
    expect(document.title).toBe("Pamoja Party");
  });

  it("colours the kit from the party's primary and secondary colours", async () => {
    stubApi({ "GET /site/": { name: "Pamoja Party", primary_colour: "#0b5d3b", secondary_colour: "#f2b705" } });
    renderApp(<BrandingProvider><span /></BrandingProvider>);

    const root = document.documentElement.style;
    await waitFor(() => expect(root.getPropertyValue("--party-primary")).toBe("#0B5D3B"));
    expect(root.getPropertyValue("--party-primary-hover")).toBe("#08442B");
    expect(root.getPropertyValue("--party-accent")).toBe("#F2B705");
  });

  it("is not hard-coded anywhere in the source", () => {
    const root = resolve(process.cwd(), "src");
    const naming = globSync("**/*.{js,jsx,css}", { cwd: root }).filter((path) =>
      /mzigo/i.test(readFileSync(resolve(root, path), "utf8")),
    );

    expect(naming).toEqual([]);
  });
});
