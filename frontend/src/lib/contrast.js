// WCAG contrast, as backend/src/backend/services/branding.py checks it.
export const WHITE = "#ffffff";
export const INK = "#13201a";
export const MIN_CONTRAST = 4.5;

const linear = (c) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};

const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => linear(Number.parseInt(hex.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export const isHex = (value) => /^#[0-9a-fA-F]{6}$/.test(value);

/** Contrast ratio of two #rrggbb colours, from 1 to 21. */
export function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}
