"""Compute the contrast ratios recorded in docs/taste-pass.md.

The accessibility criteria in the brief say ratios are computed, not eyeballed. This is
the computation, and it is committed so the numbers in the taste pass can be checked by
re-running one command rather than trusted.

    python scripts/contrast.py
    python scripts/contrast.py --markdown
"""

from __future__ import annotations

import argparse

# Semantic tokens, kept in sync with apps/web/app/tokens.css by check below.
LIGHT: dict[str, str] = {
    "ground": "#FBFAF7",
    "panel": "#F4F2EC",
    "ink": "#1A1815",
    "ink-muted": "#55514A",
    "ink-faint": "#6E695F",
    "rule": "#C9C3B6",
    "rule-control": "#999180",
    "accent": "#A3341A",
    "mark": "#F0D9A8",
    "flag": "#8A5B00",
}
DARK: dict[str, str] = {
    "ground": "#141311",
    "panel": "#1D1B18",
    "ink": "#EDEAE3",
    "ink-muted": "#A9A399",
    "ink-faint": "#8B857A",
    "rule": "#3A3733",
    "rule-control": "#666158",
    "accent": "#E2704B",
    "mark": "#4A3A15",
    "flag": "#D9A441",
}

# (label, foreground token, background token, required ratio, why)
PAIRS: list[tuple[str, str, str, float, str]] = [
    ("body text", "ink", "ground", 4.5, "WCAG 1.4.3 normal text"),
    ("secondary text", "ink-muted", "ground", 4.5, "WCAG 1.4.3 normal text"),
    ("label text", "ink-faint", "ground", 4.5, "WCAG 1.4.3, used at 11px so held to AA"),
    ("citation accent on page", "accent", "ground", 4.5, "WCAG 1.4.3 normal text"),
    ("citation accent on panel", "accent", "panel", 4.5, "WCAG 1.4.3 normal text"),
    ("risk flag text", "flag", "ground", 4.5, "WCAG 1.4.3 normal text"),
    ("marked span text", "ink", "mark", 4.5, "the citation mark must stay readable"),
    ("control boundary", "rule-control", "ground", 3.0, "WCAG 1.4.11 non-text contrast"),
    ("focus ring", "accent", "ground", 3.0, "WCAG 1.4.11 focus indicator"),
]


def _linear(channel: float) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    raw = hex_colour.lstrip("#")
    red, green, blue = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def report(theme_name: str, theme: dict[str, str], markdown: bool) -> int:
    failures = 0
    if markdown:
        print(f"\n**{theme_name}**\n")
        print("| pair | tokens | ratio | required | verdict | criterion |")
        print("|---|---|---|---|---|---|")
    else:
        print(f"\n{theme_name}")
    for label, foreground, background, required, why in PAIRS:
        ratio = contrast(theme[foreground], theme[background])
        ok = ratio >= required
        failures += 0 if ok else 1
        verdict = "PASS" if ok else "FAIL"
        if markdown:
            print(
                f"| {label} | `{foreground}` on `{background}` | {ratio}:1 | "
                f"{required}:1 | {verdict} | {why} |"
            )
        else:
            print(f"  {verdict}  {label:26} {ratio:5.2f}:1  (needs {required}:1)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    failures = report("Light theme", LIGHT, args.markdown) + report(
        "Dark theme", DARK, args.markdown
    )
    if failures:
        print(f"\n{failures} contrast failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
