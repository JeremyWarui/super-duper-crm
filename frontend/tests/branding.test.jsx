/** Every header shows the site name from the website settings, never a product name. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { BrandingProvider, applyBranding, fromSettings } from "@/theme/branding";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the site's branding", () => {
  it("names the site from its settings on the sign-in page and in the tab title", async () => {
    stubApi({ "GET /site/": { name: "Jane for Kasarani", logo_url: "" } });
    renderApp(<Login />);

    expect(await screen.findByText("Jane for Kasarani")).toBeInTheDocument();
    expect(document.title).toBe("Jane for Kasarani");
  });

  it("colours the kit from the site's primary and secondary colours", async () => {
    stubApi({ "GET /site/": { name: "Jane for Kasarani", primary_colour: "#0b5d3b", secondary_colour: "#f2b705" } });
    renderApp(<BrandingProvider><span /></BrandingProvider>);

    const root = document.documentElement.style;
    await waitFor(() => expect(root.getPropertyValue("--brand-primary")).toBe("#0B5D3B"));
    expect(root.getPropertyValue("--brand-primary-hover")).toBe("#08442B");
    expect(root.getPropertyValue("--brand-accent")).toBe("#F2B705");
  });

  it("shows the logo as the tab icon, or the tile letters when there is no logo", () => {
    applyBranding(fromSettings({ name: "Wanjiru Kamau", short_name: "Wanjiru", primary_colour: "#0b5d3b" }));
    const icon = document.querySelector("link[rel=icon]");
    expect(decodeURIComponent(icon.href)).toContain(">WK<");
    expect(decodeURIComponent(icon.href)).toContain("#0B5D3B");

    applyBranding(fromSettings({ name: "Umoja", logo_url: "https://example.com/logo.png" }));
    expect(document.querySelectorAll("link[rel=icon]")).toHaveLength(1);
    expect(document.querySelector("link[rel=icon]").href).toBe("https://example.com/logo.png");
  });

  it("marks the logo tile with the short name only when it fits, else the name's initials", () => {
    expect(fromSettings({ name: "Orange Democratic Movement", short_name: "ODM" }).shortName).toBe("ODM");
    expect(fromSettings({ name: "Wanjiru Kamau", short_name: "Wanjiru" }).shortName).toBe("WK");
    expect(fromSettings({ name: "Umoja", short_name: "" }).shortName).toBe("U");
    expect(fromSettings({ name: "Umoja", short_name: " ODM " }).shortName).toBe("ODM");
  });

  it("keeps working when the name starts with an emoji", () => {
    const b = fromSettings({ name: "😀 Umoja", short_name: "" });
    expect(b.shortName).toBe("😀U");
    expect(() => applyBranding(b)).not.toThrow();
  });

  it("is not hard-coded anywhere in the source", () => {
    const root = resolve(process.cwd(), "src");
    const naming = globSync("**/*.{js,jsx,css}", { cwd: root }).filter((path) =>
      /mzigo/i.test(readFileSync(resolve(root, path), "utf8")),
    );

    expect(naming).toEqual([]);
  });
});
