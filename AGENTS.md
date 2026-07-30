# observable-cuso4d

Observable Framework dashboards over [CPI](../CPI). CPI stays a dependency-free
library; this is where its consumers live.

## Invariants

**Personal data never enters git.** `dist/` and `src/.observablehq/` contain real
watch history. The cache sits under the source root, so ignore patterns for it must
be anchored (`src/.observablehq/`, not `.observablehq/`).

**Loaders fail loudly.** They run at build time with no terminal attached, so a
missing `CPI_PIPEPIPE_EXPORTS` must exit non-zero. Emitting `[]` would render as a
plausible "nothing watched" dashboard.

**Don't reimplement CPI here.** Anything encoding an app's semantics belongs in
CPI, where it is tested. Loaders should be flattening and renaming, nothing more.

**Filtering is a presentation choice.** The uploader denylist lives in the loaders,
never in CPI — the library must report what the archive says. Loaders report how
many rows they withheld so pages can say so instead of showing totals that disagree
with the archive.

**Framework's cache only tracks the loader script.** Freshness is the cached
output's mtime versus the loader's; files a loader opens at runtime are invisible to
it. Any such input needs `scripts/refresh.py` extended to drop the affected cache
entries, and it must compare by *value* — an mtime check silently fails to restore
full data when the input is deleted rather than edited. This cannot be done inside a
loader, since a loader only runs once Framework has already decided to run it.

**Inline `${...}` cannot span blank lines.** A multi-line inline expression ends the
Markdown paragraph and the remainder renders as literal source. Use a JS block with
`display()` for anything conditional.

## Plot traps hit so far

**`percent: true` is a scale transform.** It multiplies by 100 *before* the scale, so
an explicit domain belongs in percent space: `domain: [0, 100]` for data in 0..1.
Writing `[0, 1]` shows only the first 1% of the data. Bin thresholds stay in 0..1,
since mark transforms run before scale transforms.

**`thresholds: n` bins linearly.** On a log axis that is wrong, not merely coarse:
for video lengths it put 88% of the data in one bar spanning most of the width, and
for watch lag it hid a genuine bimodal split entirely. Pass explicit log-spaced
thresholds, e.g. `d3.range(0, 25).map((i) => 0.25 * 2 ** (i / 2))`.

**Pin the domain from the data.** Hardcoded bounds silently clip: `[0.2, 600]` cut
off videos past ten hours and left dead space on the left. Use `d3.max`.

**Check a heuristic against the data before shipping it.** Detecting pasted video
ids by "11 characters of `[\w-]`" matches `speculation` and `さくら荘のペットな彼女`;
only bilibili's `BV` prefix is actually distinguishable. Claims about shape
(bimodal, spike, cluster) need the same treatment — the completion histogram has one
peak and a flat tail, not the two peaks it looks like it should have.

**Charts must be sound for the data that exists.** See below — with one snapshot,
a per-day chart is not a rough chart, it is a wrong one.

## Structure

    src/lib/              plumbing shared across sources
    src/<source>/*.md     pages; JS blocks with Plot
    src/<source>/data/    loaders for that source

One directory per source, nesting as a Framework section. A page that is a *view of*
a source belongs inside it (`/video/fandoms`), not beside it.

File-based routing: `src/video/data/videos.json.py` serves `./data/videos.json`
relative to the page, reached via `FileAttachment("./data/videos.json")` — which only
accepts a static string literal, since Framework decides what to run by static
analysis. Loaders run with only their own directory on `sys.path`, so importing from
`src/lib` needs an explicit insert.

## Working here

`nix develop`, then `CPI_PIPEPIPE_EXPORTS=... npm run build`. Run a loader directly
to debug it: `python src/data/videos.json.py | head -c 500`.

ruff and nixfmt run from the pre-commit hook. When checking a formatter's exit
status by hand, don't pipe it through `grep` first — you will read grep's status.

## What the data cannot support

PipePipe keeps one history row per video, overwriting its timestamp on every play,
so only the last watch survives in any export.

- Time spent is a range, never a number. Each video once is a floor; weighting by
  the play counter is a ceiling far above reality, as that counter increments on
  replays, seeks and background loops (one 11-minute video sits at 3543).
- No per-day or per-week charts until several snapshots exist. One snapshot spreads
  years of watching across scattered last-watched dates.
- Live streams store `0` or `-1` for duration, meaning unknown. `CPI` surfaces that
  as `None`; keep it out of length and total-time charts rather than treating it
  as zero.
- Some upload dates are derived from relative strings ("3 days ago"). Filter on
  `uploaded_is_approximate` before any chart keyed on upload time.
