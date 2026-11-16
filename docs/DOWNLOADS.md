# Complete current downloads

`complete-queries.zip` contains the complete permitted queries, normalized inputs,
source and review receipts, code, tests, documentation, reports and figures.
It is not a metadata-only package. Historical original HTML/PDF caches are
excluded; normalized historical evidence is retained.

`substack-figures.zip` contains upload-ready figures and the **exact same**
complete query ZIP, named `complete-query-set.zip`. Extract that nested archive
to open `publication/report.html` or the full-characteristics successor at
`publication/characteristics-v5/report.html`. Reports work locally; the successor
includes all 1,284 candidates and all fifteen trait fields.

The large earlier report and standalone historical trait tables are not
duplicated outside the nested query ZIP. This avoids GitHub's 100-MiB single-file
limit without dropping any research evidence. The successor report, figures and
plot tables also appear under `characteristics-v5/` in the figure archive.
Its full relative-path evidence links work after extracting the complete queries.
The frozen V1-V4 reports remain under their original publication directories.
The V2-V5 trait tables reference unchanged literals and receipts by 1-based
`baseline_trait_row` into the complete frozen v1 JSONL. Both tables are
included: this is lossless relational storage, not a metadata-only download.

Large text members in both ZIPs use standard **ZIP-LZMA** compression;
other entries use Deflate. This retains every original file byte while keeping
both downloads below GitHub's limit. Some desktop ZIP utilities do not support
LZMA. Python 3's standard library extracts the complete archive:

```bash
python3 -m zipfile -e complete-queries.zip complete-queries
```

The archive includes the 6,735-cell frozen V3, V4 and V5 research queues, all historical
normalized evidence, new source claims, original-byte hash/retrieval receipts,
and every frozen V1-V4 result. Raw HTML/PDF/XLSX caches are not required.

With the project's pinned environment, normalized-input replay is:

```bash
python -m which_candidate.house_project --evidence-only
```

This refreshes evidence and the separately versioned successor. It does not refit
the earlier frozen analyses, require historical raw caches, or deploy a website.
The SHA256 and byte count of each complete download are in `downloads.json`.
