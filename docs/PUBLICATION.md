# Current publication figures

The only chart set is `publication/`, containing nine current figures for
Substack and Margin of Error. Superseded plot directories and their download
bundles have been removed from the checkout; Git history retains them.
Historical analysis data under `results/` are unchanged; `results/house/` adds the
complete current House roster and source-qualified candidate information.
`results/members/` separately accounts for all 435 sitting seats, six nonvoting
seats, provisional incoming members and historical CongressData observations.
It does not change the election-candidate denominator in the existing charts.
Website publication remains withdrawn.

All nine figures concern the **House only**, including the seat-baseline
and incumbency-history plots. The evidence figure counts every named candidate,
not only the selected Democratic analysis candidate. Its all-party denominators
and coverage are generated directly from `results/house/coverage.json`.
See [candidate information and limitations](HOUSE_CANDIDATES.md).

The UK Decline `vizstyle` helpers and two rendered GDP/income comparisons were
the visual references: warm paper, serif hierarchy, restrained colors, direct
labels and meaningful reference lines, without decorative dashboard elements.

The current design includes:

- The same-candidate donor/voting comparison now uses identical symmetric limits,
  placing zero in the middle of both panels. Opposite associations are visually
  apparent without comparing positions on differently cropped axes. Predictor
  increments remain different and explicit; aligned outcome axes do not turn
  the scores into the same construct or establish causal effects.
- Low-support donor and unavailable-caucus labels move clear of the zero line.
  The unsupported donor estimate remains excluded from the headline plot and
  complete in its CSV; missing caucus rosters remain explicitly unavailable.

The new six-characteristic figure puts incumbency, prior voting ideology, party
defection, age, service and source-recorded gender on a common margin-point
outcome scale. Predictor increments remain explicit and are not comparable
candidate-quality scores. Pointwise intervals and six-test Holm p-values are
distinguished. `results/house-study/` supplies the exact current fits, common-map
benchmark sensitivities and state/person-held-out diagnostics.

`publication/report.html` is a local, offline-capable research report, **not a
website redeployment**. It contains the findings and figures plus searchable
candidate, sitting-seat and incoming-seat views. Source evidence and filtered
CSV exports are available without a server; only external source links require
network access. The same report is included in both downloads.

Each theme has nine PNG/SVG exports. Shared `plot-data/`, `captions.json` and
`manifest.json` provide exact plotted values, captions, alt text and checksums.
The `publication-charts` skill requires matching scales for comparable panels,
collision-free labels, fresh source-hashed reading-width previews and one
current publication folder rather than accumulating design versions.

Reproduce the figures and complete downloads:

```bash
.venv/bin/python -m which_candidate.rebuild_publication
.venv/bin/python -m which_candidate.rebuild_package
```

The builders stage complete outputs before refreshing the same destinations.
Unchanged bytes are reused, obsolete files in the theme/data folders are removed,
and failed rendering or archive generation leaves existing outputs intact.
`--output` remains available for an independent replay or test directory.

`downloads/complete-queries.zip` contains all normalized research records,
evidence, models, code, tests and current figure inputs, not merely metadata.
`downloads/substack-figures.zip` embeds that exact query ZIP along with the
current Substack exports. Neither bundle includes superseded plots.
`downloads/downloads.json` records both archive sizes and checksums.

After extracting the query ZIP, replay the analysis and figures without network:

```bash
.venv/bin/python -m which_candidate.rebuild replay --output replay-analysis
.venv/bin/python -m which_candidate.house_candidates --output replay-house
.venv/bin/python -m which_candidate.house_members --output replay-members
.venv/bin/python -m which_candidate.house_study --output replay-study
.venv/bin/python -m which_candidate.rebuild_publication --output replay-figures
```

For an in-place complete rebuild, use
`python -m which_candidate.house_project`. It replays normalized inputs and
refreshes all current House tables, the study, figures, report and both packages.

Public replay reconstructs the normalized analysis and current figures, not the
original website extraction process. Historical audit receipts describe the
commits at which they were recorded, not the current publication file layout.
Legacy publication tests requiring superseded image fixtures run in the full
checkout and skip in the current-chart download; current replay tests run in both.
