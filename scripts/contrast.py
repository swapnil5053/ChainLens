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

NEUTRAL_HUE = 262.0
ACCENT_HUE = 256.0

LIGHT: dict[str, Oklch] = {
    "ground": (0.994, 0.0015, NEUTRAL_HUE),
    "panel": (0.972, 0.004, NEUTRAL_HUE),
    "panel-raised": (0.948, 0.006, NEUTRAL_HUE),
    "ink": (0.24, 0.015, NEUTRAL_HUE),
    "ink-muted": (0.455, 0.02, NEUTRAL_HUE),
    "ink-faint": (0.55, 0.022, NEUTRAL_HUE),
    "line": (0.905, 0.008, NEUTRAL_HUE),
    "line-strong": (0.66, 0.02, NEUTRAL_HUE),
    "accent": (0.46, 0.15, ACCENT_HUE),
    "accent-weak": (0.93, 0.045, ACCENT_HUE),
    "flag": (0.52, 0.15, 32.0),
}

DARK: dict[str, Oklch] = {
    "ground": (0.155, 0.012, NEUTRAL_HUE),
    "panel": (0.195, 0.014, NEUTRAL_HUE),
    "panel-raised": (0.24, 0.016, NEUTRAL_HUE),
    "ink": (0.95, 0.008, NEUTRAL_HUE),
    "ink-muted": (0.73, 0.016, NEUTRAL_HUE),
    "ink-faint": (0.63, 0.018, NEUTRAL_HUE),
    "line": (0.3, 0.014, NEUTRAL_HUE),
    "line-strong": (0.485, 0.02, NEUTRAL_HUE),
    "accent": (0.72, 0.13, ACCENT_HUE),
    "accent-weak": (0.3, 0.05, ACCENT_HUE),
    "flag": (0.74, 0.15, 42.0),
}

PAIRS: list[tuple[str, str, str, float, str]] = [
    ("body text", "ink", "ground", 4.5, "WCAG 1.4.3"),
    ("secondary text", "ink-muted", "ground", 4.5, "WCAG 1.4.3"),
    ("faint text", "ink-faint", "ground", 4.5, "WCAG 1.4.3"),
    ("accent on ground", "accent", "ground", 4.5, "WCAG 1.4.3"),
    ("accent on panel", "accent", "panel", 4.5, "WCAG 1.4.3"),
    ("ink on citation mark", "ink", "accent-weak", 4.5, "the mark must stay readable"),
    ("risk flag text", "flag", "ground", 4.5, "WCAG 1.4.3"),
    ("meaningful boundary", "line-strong", "ground", 3.0, "WCAG 1.4.11"),
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
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


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
                print(
                    f"  --{token:14} oklch({colour[0]} {colour[1]} {colour[2]})  {to_hex(colour)}"
                )

    failures = report("Light theme", LIGHT, args.markdown) + report(
        "Dark theme", DARK, args.markdown
    )
    if failures:
        print(f"\n{failures} contrast failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
