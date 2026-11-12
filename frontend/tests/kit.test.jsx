/** The UI kit's components load through the `@` alias and carry the party tokens. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button, ButtonShape } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";

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
});
