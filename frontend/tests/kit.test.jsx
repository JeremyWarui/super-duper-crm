/** The UI kit's components load through the `@` alias and carry the party tokens. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button, ButtonShape } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { Reveal } from "@/components/ui/reveal";

describe("the UI kit", () => {
  it("gives a button the shell's shape unless it names one: pills on the website, rounded in the apps", () => {
    render(
      <>
        <Button>Site</Button>
        <ButtonShape.Provider value="rounded">
          <Button>App</Button>
          <Button shape="pill">Named</Button>
        </ButtonShape.Provider>
      </>,
    );
    expect(screen.getByRole("button", { name: "Site" })).toHaveClass("rounded-full");
    expect(screen.getByRole("button", { name: "App" })).toHaveClass("rounded-lg");
    expect(screen.getByRole("button", { name: "Named" })).toHaveClass("rounded-full");
  });

  it("renders a primary button on the party colour at the 44px touch height", () => {
    render(<Button>Join the party</Button>);

    const button = screen.getByRole("button", { name: "Join the party" });
    expect(button.className).toMatch(/\bbg-primary\b/);
    expect(button.className).toMatch(/\bh-11\b/);
  });

  it("draws a select on white with its down arrow", () => {
    render(<NativeSelect aria-label="County"><option>All counties</option></NativeSelect>);

    const select = screen.getByRole("combobox", { name: "County" });
    expect(select.className.split(" ")).toEqual(expect.arrayContaining(["bg-white", "bg-[image:var(--select-chevron)]"]));
  });

  it("shows a spinner on a loading button and holds it until the action ends", () => {
    render(<Button loading>Saving…</Button>);

    const button = screen.getByRole("button", { name: "Saving…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button.querySelector('[data-slot="spinner"]')).not.toBeNull();
  });
});

describe("the scroll reveal", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps a section down until it scrolls on screen, then slides it in", () => {
    let report;
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback) { report = callback; }
      observe() {}
      disconnect() {}
    });
    render(<Reveal><p>Where we stand</p></Reveal>);
    const section = screen.getByText("Where we stand").parentElement;
    expect(section).toHaveAttribute("data-reveal", "out");

    act(() => report([{ isIntersecting: true, boundingClientRect: { bottom: 400 } }]));
    expect(section).toHaveAttribute("data-reveal", "in");
  });

  it("shows a section at once where the browser cannot watch scrolling", () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    render(<Reveal><p>Where we stand</p></Reveal>);
    expect(screen.getByText("Where we stand").parentElement).toHaveAttribute("data-reveal", "in");
  });
});
