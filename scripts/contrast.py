"""Compute the contrast ratios recorded in the accessibility audit.

The criteria say ratios are computed, not eyeballed. This is the computation, committed so
the numbers can be re-derived by running one command rather than trusted. Colours are
declared in OKLCH, matching apps/web/src/styles/tokens.css, and converted here rather than
maintained twice as hex.

    python scripts/contrast.py
    python scripts/contrast.py --markdown
"""

from __future__ import annotations

import argparse
import math

Oklch = tuple[float, float, float]

NEUTRAL_HUE = 85.0
ACCENT_HUE = 42.0

LIGHT: dict[str, Oklch] = {
    "ground": (0.985, 0.004, NEUTRAL_HUE),
    "panel": (0.962, 0.008, NEUTRAL_HUE),
    "panel-raised": (0.935, 0.010, NEUTRAL_HUE),
    "ink": (0.205, 0.010, NEUTRAL_HUE),
    "ink-muted": (0.455, 0.012, NEUTRAL_HUE),
    "ink-faint": (0.545, 0.014, NEUTRAL_HUE),
    "rule": (0.845, 0.014, NEUTRAL_HUE),
    "rule-control": (0.654, 0.018, NEUTRAL_HUE),
    "accent": (0.480, 0.140, ACCENT_HUE),
    "mark": (0.900, 0.062, 92.0),
    "flag": (0.500, 0.090, 75.0),
}

DARK: dict[str, Oklch] = {
    "ground": (0.185, 0.008, NEUTRAL_HUE),
    "panel": (0.228, 0.010, NEUTRAL_HUE),
    "panel-raised": (0.272, 0.011, NEUTRAL_HUE),
    "ink": (0.930, 0.010, NEUTRAL_HUE),
    "ink-muted": (0.720, 0.012, NEUTRAL_HUE),
    "ink-faint": (0.625, 0.013, NEUTRAL_HUE),
    "rule": (0.330, 0.012, NEUTRAL_HUE),
    "rule-control": (0.496, 0.014, NEUTRAL_HUE),
    "accent": (0.700, 0.130, ACCENT_HUE),
    "mark": (0.330, 0.055, 92.0),
    "flag": (0.780, 0.110, 80.0),
}

PAIRS: list[tuple[str, str, str, float, str]] = [
    ("body text", "ink", "ground", 4.5, "WCAG 1.4.3"),
    ("secondary text", "ink-muted", "ground", 4.5, "WCAG 1.4.3"),
    ("field label, 11px", "ink-faint", "ground", 4.5, "WCAG 1.4.3, held to AA not large-text"),
    ("citation accent on page", "accent", "ground", 4.5, "WCAG 1.4.3"),
    ("citation accent on panel", "accent", "panel", 4.5, "WCAG 1.4.3"),
    ("risk flag text", "flag", "ground", 4.5, "WCAG 1.4.3"),
    ("marked span text", "ink", "mark", 4.5, "the citation mark must stay readable"),
    ("control boundary", "rule-control", "ground", 3.0, "WCAG 1.4.11"),
    ("focus ring", "accent", "ground", 3.0, "WCAG 1.4.11"),
]


def oklch_to_srgb(colour: Oklch) -> tuple[float, float, float]:
    lightness, chroma, hue = colour
    radians = math.radians(hue)
    a = chroma * math.cos(radians)
    b = chroma * math.sin(radians)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    long, medium, short = l_**3, m_**3, s_**3
    red = 4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short
    green = -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short
    blue = -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short

    def encode(channel: float) -> float:
        clamped = max(0.0, min(1.0, channel))
        return 12.92 * clamped if clamped <= 0.0031308 else 1.055 * clamped ** (1 / 2.4) - 0.055

    return encode(red), encode(green), encode(blue)


def to_hex(colour: Oklch) -> str:
    r, g, b = oklch_to_srgb(colour)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(colour: Oklch) -> float:
    r, g, b = oklch_to_srgb(colour)
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(first: Oklch, second: Oklch) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def report(name: str, theme: dict[str, Oklch], markdown: bool) -> int:
    failures = 0
    if markdown:
        print(f"\n**{name}**\n")
        print("| pair | tokens | ratio | required | verdict | criterion |")
        print("|---|---|---|---|---|---|")
    else:
        print(f"\n{name}")
    for label, foreground, background, required, criterion in PAIRS:
        ratio = contrast(theme[foreground], theme[background])
        passed = ratio >= required
        failures += 0 if passed else 1
        verdict = "PASS" if passed else "FAIL"
        if markdown:
            print(
                f"| {label} | `{foreground}` on `{background}` | {ratio}:1 | {required}:1 | "
                f"{verdict} | {criterion} |"
            )
        else:
            print(f"  {verdict}  {label:26} {ratio:6.2f}:1  (needs {required}:1)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--hex", action="store_true", help="print the sRGB equivalents")
    args = parser.parse_args()

    if args.hex:
        for name, theme in (("light", LIGHT), ("dark", DARK)):
            print(f"\n{name}")
            for token, colour in theme.items():
                print(f"  --{token:14} oklch({colour[0]} {colour[1]} {colour[2]})  {to_hex(colour)}")

    failures = report("Light theme", LIGHT, args.markdown) + report("Dark theme", DARK, args.markdown)
    if failures:
        print(f"\n{failures} contrast failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
