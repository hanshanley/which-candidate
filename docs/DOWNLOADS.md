# Complete current downloads

`complete-queries.zip` contains the complete permitted queries, normalized inputs,
source and review receipts, code, tests, documentation, reports and figures.
It is not a metadata-only package. Historical original HTML/PDF caches are
excluded; normalized historical evidence is retained.

`substack-figures.zip` contains upload-ready figures and the **exact same**
complete query ZIP, named `complete-query-set.zip`. Extract that nested archive
to open `publication/report.html` or the full-characteristics successor at
`publication/characteristics-v2/report.html`. Reports work locally; the successor
includes all 1,284 candidates and all fifteen trait fields.

The large earlier report and standalone historical trait tables are not
duplicated outside the nested query ZIP. This avoids GitHub's 100-MiB single-file
limit without dropping any research evidence. The successor report, figures and
plot tables also appear under `characteristics-v2/` in the figure archive.
Its full relative-path evidence links work after extracting the complete queries.
The frozen v1 report is retained under `publication/characteristics-v1/`.
The v2 trait table references unchanged literals and receipts by 1-based
`baseline_trait_row` into the complete frozen v1 JSONL. Both tables are
included: this is lossless relational storage, not a metadata-only download.

With the project's pinned environment, normalized-input replay is:

```bash
python -m which_candidate.house_project --evidence-only
```

This refreshes evidence and the separately versioned successor. It does not refit
the earlier frozen analyses, require historical raw caches, or deploy a website.
The SHA256 and byte count of each complete download are in `downloads.json`.
