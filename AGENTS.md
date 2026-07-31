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

**A channel name is a column name.** `fill: "asleep"` looks like a constant but is a
lookup, so a name that is not a column yields undefined for every row and the mark
draws nothing — axes, title and legend all render, so the page looks finished. To
stack two measures held in separate columns, reshape to long form (one row per
category) rather than layering two marks with `y1`/`y2`.

**Never read clock fields off a `Date` in a page.** `getHours`, `getDay` and
`toISOString` all convert to whatever timezone the *browser* is in, which is not where
the data was recorded. On a UTC machine an 01:58+08:00 bedtime displayed as 18:06, an
evening — a plausible number, wrong by eight hours. Loaders emit offset-bearing ISO
strings; slice the characters, or anchor at UTC explicitly.

**`type: "utc"` needs UTC-anchored dates.** `new Date("2026-07-30T00:00")` is midnight
where the browser is, which a utc axis renders as the 29th for anyone east of UTC.
Append `Z` when parsing a date-only string for a time axis.

**Two series on one axis need one convention.** Bedtime past midnight was noon-shifted
(so 01:00 read as 25) while waking was raw, putting a 22:00 wake and a 22:00 bedtime at
the same height with opposite meanings. Derive the second from the first rather than
reading each off the clock independently.

**Charts must be sound for the data that exists.** See below — for PipePipe, with one
snapshot, a per-day chart is not a rough chart, it is a wrong one. What a source can
support is a fact about that source, so check the section for the one you are
plotting rather than carrying a limit across.

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

Per source, since these follow from how each app stores its data. Nothing here
generalizes to a source not named.

### PipePipe

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

### Gadgetbridge

The opposite storage model: samples accumulate, one immutable row per minute, so a
single export already holds the full history. Per-day and per-week charts are sound
here — the PipePipe limit above does not apply. Snapshots still matter, but only
because the band buffers about a week and drops what was never synced.

- Sample rows are not minutes. Some are sub-minute rows written during a live heart
  rate measurement, so counting rows overstates coverage — one month came out at
  110%. Count distinct minutes.
- Days with no data and days spent not wearing the band are not zero-step days.
  Divide by worn time, and let a page say how much was excluded.
- Deep sleep is systematically low (~10% of sleep, against 13-23% typical). That is
  this band's staging through Gadgetbridge, not a finding about the sleeper.
- No workouts, SpO2, PAI or resting heart rate: those tables are empty. Resting
  heart rate has to be derived from sleeping minutes.
- The 5-minute stress series claims 0-100 but has a few values above 250.
