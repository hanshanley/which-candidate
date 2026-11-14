# 2026 figure refinement

The active chart set is `publication/2026-v5/`. This is a visual-only revision:
all estimates, intervals, candidate records and plotted CSVs are unchanged from
v4. Both v4 download archives and every v4 publication/analysis file are preserved.
Website publication remains withdrawn.

The UK Decline `vizstyle` helpers and two rendered GDP/income comparisons were
the visual references: warm paper, serif hierarchy, restrained colors, direct
labels and meaningful reference lines, without decorative dashboard elements.

Two targeted repairs:

- The same-candidate donor/voting comparison now uses identical symmetric limits,
  placing zero in the middle of both panels. Opposite associations are visually
  apparent without comparing positions on differently cropped axes. Predictor
  increments remain different and explicit; aligned outcome axes do not turn
  the scores into the same construct or establish causal effects.
- Low-support donor and unavailable-caucus labels move clear of the zero line.
  The unsupported donor estimate remains excluded from the headline plot and
  complete in its CSV; missing caucus rosters remain explicitly unavailable.

The other five PNGs are unchanged. Each theme has eight PNG/SVG exports, exact
plotted CSVs and captions. The updated `publication-charts` skill requires
matching scales for comparable panels, collision-free diagnostic labels, fresh
source-hashed reading-width previews and preservation of frozen releases.

Reproduce the figures and complete downloads:

```bash
.venv/bin/python -m which_candidate.rebuild_publication --version 2026-v5
.venv/bin/python -m which_candidate.rebuild_package --version 2026-v5
```

The default v4 figure command remains unchanged for backward compatibility.
The v5 query archive contains all normalized research records, evidence, models,
code, tests and figure inputs, not merely metadata. The Substack bundle embeds
that exact complete-query ZIP. Public replay reconstructs the normalized
analysis and figures, not the original website extraction process.
The query archive also includes the frozen v4 comparison figures needed by the
regression tests; the upload-ready images remain the v5 figures.
