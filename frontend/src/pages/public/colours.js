/** The party's two colours as CSS variables for a page wrapper's style attribute. */
export function partyColours(party) {
  return { "--color-primary": party?.primary_colour, "--party-secondary": party?.secondary_colour };
}
