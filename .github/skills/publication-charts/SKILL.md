---
name: publication-charts
description: Build and repair beautiful, understated, evidence-led publication charts for Margin of Error, Substack and research projects. Use for chart creation, redesign, beautification, or visual audits; inspect rendered outputs and fix both statistical and design defects.
---

# Evidence-led publication charts

Use the user's established UK Decline visual language, not a generic dashboard.
The goal is an informative editorial graphic, not a styled statistical dump.

## Before drawing

1. Read the project's instructions and existing chart code. Inspect two actual
   rendered examples and their plotting helpers; do not copy appearance from
   filenames or assume a successful export means a good figure.
2. Where available, inspect `uk_decline/vizstyle`, its `europe_data` charts and
   the published examples in `margin_of_error`. Reuse the current project's
   helpers when they are sound; avoid a dependency on another local checkout.
3. State the question, population, outcome, units, comparison and time window.
   Audit joins, missingness and denominator definitions before styling.
4. Choose one central comparison per graphic. Split unrelated scales or
   populations into separate figures or clearly aligned small multiples.
   Never display unlike coefficient increments as a ranked candidate score.

## House style

- Warm paper: Substack `#F7F5F0`; Margin of Error `#F2EFE7`.
- Ink `#1A1A1A`, secondary text `#6B6B6B`, restrained grid `#D6D3CC`.
- Terracotta `#C85A3D` for the focal series, blue `#3D6F8C` for a comparator.
  Add colors only when additional categories need them; keep meanings stable.
- Use tasteful serif typography for editorial charts, with clear hierarchy.
  A short title, one explanatory subtitle and compact notes beat a giant
  headline, dense paragraph and tiny footnote.
- Prefer a roughly 3:2 landscape canvas. Give data the majority of the area.
  At a 1200-pixel reading width, aim for a 28-34-pixel title, 17-20-pixel body,
  and notes no smaller than about 13 pixels. Adjust layout, not just font size,
  if text does not fit.
- Remove unnecessary spines and tick marks. Use light gridlines only on the
  value axis; emphasize zero for differences. Bars start at zero.
- Prefer direct labels and short category names to legends and abbreviations.
  Show exact counts or sample sizes where they affect interpretation.
- No decorative arrows, badges, gradients, shadows, oversized metric callouts,
  gratuitous icons, fake hand-drawn effects, or repeated paragraphs of caveats.

## Statistical and visual integrity

- Label percentage points versus percentages and vote share versus margin.
  Do not convert an interval using a different scale from its estimate.
- Show observed points honestly. Model lines require supported ranges;
  uncertainty must describe the actual estimator, not polling MOE or raw SD.
- Missing values are not zero, negative labels or a reference identity.
  Preserve gaps and distinguish measured absence from unavailable evidence.
- Use common samples and scales for sensitivity comparisons. Disclose changed
  cohorts, geography and sources in historical comparisons.
- Do not infer religion, race or gender from names, photos, geography, relatives
  or a website's generic mentions. Do not silently promote machine-extracted
  facts into verified labels.
- Keep sparse, high-leverage or unsupported fits out of headline inference.
  An honest coverage graphic is better than a spurious ranking.
- Derive headlines from results; do not hard-code "no effect," "significant,"
  rankings or trends that can become false when inputs change.

## Render, inspect, repair

1. Export PNG and vector SVG with deterministic metadata, plus exact plotted
   CSV data, captions, alt text and source hashes.
2. Check clipping, title/subtitle collisions, tick-label overlap, annotation
   collisions, excessive whitespace and accidental image-width expansion.
   Measure text extents where possible; those tests do not replace inspection.
3. Inspect every actual figure at a normal article width, plus a small-screen
   preview. Open individual images, not only a contact sheet. Ask: what does
   a reader learn in five seconds, and can every visible number be explained?
4. Fix dense labels, unreadable notes, unsupported emphasis and weak comparisons,
   then rerender and inspect again. Do not call a figure beautiful merely
   because it uses the palette.
5. Verify the two publication backgrounds preserve all non-background content.
   Read the SVG text as a second check of labels, units and sample sizes.
6. Deliver complete query/data downloads, not metadata-only packages. Verify
   extracted replay and downloaded public bytes when publishing artifacts.

## Finishing

Audit source evidence, estimates, figures and prose together. Write concrete
findings with affected files/data, fix actionable issues, rerun focused and
full checks as appropriate, and identify genuinely unresolved data gaps.
Do not republish a withdrawn website analysis without authorization.
