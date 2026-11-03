"""Contrast of the party's colours against the text set on them."""

WHITE = "#ffffff"
INK = "#13201a"
MIN_CONTRAST = 4.5


def _channels(colour: str) -> list[int]:
    return [int(colour[i : i + 2], 16) for i in (1, 3, 5)]


def _luminance(colour: str) -> float:
    def linear(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in _channels(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two #rrggbb colours, from 1 to 21."""
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)

