# Complete current downloads

Both complete archives are assets of the `characteristics-v8` GitHub release,
not size-limited Git blobs. From the repository root, download them with:

```bash
gh release download characteristics-v8 --repo hanshanley/which-candidate \
  --dir downloads --pattern complete-queries.zip --pattern substack-figures.zip
```

`downloads/downloads.json` records their exact byte counts and SHA256 hashes;
`downloads/release-assets.json` additionally records the asset locations.
Earlier committed archives remain in Git history. Moving the current complete
archives to release assets does not remove any historical query or report.

`complete-queries.zip` contains the complete permitted queries, normalized inputs,
source and review receipts, code, tests, documentation, reports and figures.
It is not a metadata-only package. Historical original HTML/PDF caches are
excluded; normalized historical evidence is retained.

`substack-figures.zip` contains upload-ready figures and the **exact same**
complete query ZIP, named `complete-query-set.zip`. Extract that nested archive
to open `publication/report.html` or the full-characteristics successor at
`publication/characteristics-v8/report.html`. Reports work locally; the successor
includes all 1,284 candidates and all fifteen trait fields.

The large earlier report and standalone historical trait tables are not
duplicated outside the nested query ZIP. The complete historical product now
exceeds GitHub's 100-MiB single-Git-blob limit and is distributed as release
assets without dropping research evidence. The successor report, figures and
plot tables also appear under `characteristics-v8/` in the figure archive.
HTML reports are retained once, inside its exact nested complete-query archive,
rather than duplicated beside the upload-ready figures. No query or report
is removed from the complete query set.
Its full relative-path evidence links work after extracting the complete queries.
The frozen V1-V7 reports remain under their original publication directories.
The V2-V8 trait tables reference unchanged literals and receipts by 1-based
`baseline_trait_row` into the complete frozen v1 JSONL. Both tables are
included: this is lossless relational storage, not a metadata-only download.

HTML, CSV, JSON and SVG members of at least 64 KiB in both ZIPs use standard
**ZIP-LZMA** compression;
Large text members use the stronger deterministic LZMA preset 9/extreme.
JSONL gzip members and the exact nested query ZIP also use LZMA to
compress repeated archived bytes without changing their inner content.
Other entries use Deflate. This retains every archived file byte; the complete
archives are not truncated to satisfy a Git-blob size limit. Some desktop ZIP utilities do not support
LZMA. Python 3's standard library extracts the complete archive:

```bash
python3 -m zipfile -e complete-queries.zip complete-queries
```

The archive includes the 6,735-cell frozen V3, V4, V5 and V6 research queues,
the complete 19,260-cell all-party V7 and V8 queues, the current four remaining-work
queues, the CongressData variable/person review, all historical
normalized evidence, new source claims, original-byte hash/retrieval receipts,
and every frozen V1-V7 result. Raw HTML/PDF/XLSX/FST caches are not required.

With the project's pinned environment, normalized-input replay is:

```bash
python -m which_candidate.house_project --evidence-only
```

This refreshes evidence and the separately versioned successor. It does not refit
the earlier frozen analyses, require historical raw caches, or deploy a website.
The SHA256 and byte count of each complete download are in `downloads.json`.
