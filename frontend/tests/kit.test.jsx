/** The UI kit's components load through the `@` alias and carry the party tokens. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";

describe("the UI kit", () => {
  it("renders a primary button on the party colour at the 44px touch height", () => {
    render(<Button>Join the party</Button>);

    const button = screen.getByRole("button", { name: "Join the party" });
    expect(button.className).toMatch(/\bbg-primary\b/);
    expect(button.className).toMatch(/\bh-11\b/);
  });
});
