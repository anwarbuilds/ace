"""Compare local approved Analytics references with fictional running-app captures.

Requires Pillow, already used by the backend image pipeline. Output stays in
Git-ignored artifacts. Raw pixel differences include data, wording and the
preserved shell; they are diagnostic images, not a visual acceptance score.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageStat

TABS = [("01_Overview_APPROVED.png", "overview"),
        ("02_Outcomes_APPROVED.png", "outcomes"),
        ("03_Role_and_Resume_APPROVED.png", "role-resume"),
        ("04_Companies_APPROVED.png", "companies")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, default=Path("design/ace-analytics-pixel-lock/references/screenshots"))
    parser.add_argument("--captures", type=Path, default=Path("artifacts/analytics-validation"))
    args = parser.parse_args()
    sheet = Image.new("RGB", (1672, (471 + 32) * 4), "#fff9fb")
    draw = ImageDraw.Draw(sheet)
    metrics = []
    for index, (reference, tab) in enumerate(TABS):
        approved = Image.open(args.references / reference).convert("RGB")
        implemented = Image.open(args.captures / f"light-{tab}.png").convert("RGB")
        if approved.size != (1672, 941) or implemented.size != approved.size:
            raise ValueError(f"{tab} must be captured at exactly 1672 by 941")
        difference = ImageChops.difference(approved, implemented)
        error = sum(ImageStat.Stat(difference).mean) / 3
        metric = {"tab": tab, "viewport": [1672, 941], "mean_absolute_channel_error": round(error, 3)}
        initial_path = args.captures / f"initial-{tab}.png"
        if initial_path.exists():
            initial = Image.open(initial_path).convert("RGB")
            metric["initial_mean_absolute_channel_error"] = round(sum(ImageStat.Stat(ImageChops.difference(approved, initial)).mean) / 3, 3)
        metrics.append(metric)
        pair = Image.new("RGB", (3344, 973), "#fff9fb")
        pair_draw = ImageDraw.Draw(pair)
        pair_draw.text((16, 10), f"APPROVED: {tab}", fill="#27131f")
        pair_draw.text((1688, 10), "IMPLEMENTED: fictional local data, existing ACE shell", fill="#27131f")
        pair.paste(approved, (0, 32))
        pair.paste(implemented, (1672, 32))
        pair.save(args.captures / f"comparison-{tab}.png")
        ImageEnhance.Contrast(difference).enhance(2).save(args.captures / f"difference-{tab}.png")
        y = index * 503
        draw.text((12, y + 10), f"APPROVED: {tab}", fill="#27131f")
        draw.text((848, y + 10), "IMPLEMENTED: fictional local data", fill="#27131f")
        sheet.paste(approved.resize((836, 471)), (0, y + 32))
        sheet.paste(implemented.resize((836, 471)), (836, y + 32))
    sheet.save(args.captures / "comparison-contact-sheet.png")
    (args.captures / "comparison-metrics.json").write_text(json.dumps({
        "note": "Raw image diagnostics include deliberately different data, truthful unavailable labels and preserved existing ACE shell. These are not acceptance scores.",
        "tabs": metrics,
    }, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
