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

## Layout

**Every chart gets its own full-width row.** Write chart blocks as bare ```js fences
with no `<div class="grid">` or `<div class="card">` around them. Two charts sharing a
`grid-cols-2` row each lose half the horizontal axis, which is the one carrying the
data: at that width a 618-point daily series and a 28-bin histogram stop being
readable rather than merely getting cramped.

**Only stat cards go multi-column.** A `grid-cols-N` row is for cards holding one
number each — the `class="big"` rows counting days recorded or median sleep. A single
number does not care how wide its box is.

**A chart freed from a shared row can take the space as height too.** The
stress-versus-heart-rate heatmap went from 240 to 300px once it had the full width,
its y axis spanning 135bpm in 5bpm bins.

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

**A bar's category is its identity.** Two rows sharing a `y` value land in one band and
draw over each other, so the chart shows one and silently drops the other — no warning,
no visual tell. Ten of the twenty largest bookmark folders exist on both machines under
the same name, and five Firefox page titles differed only past the 22nd character of a
base64 path. Facet by whatever distinguishes them, or build a label that is unique by
construction; truncating a long label *creates* this bug where none existed.

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

### Firefox

Rows are immutable like Gadgetbridge's, so per-day charts are sound — but Firefox
deletes its own rows on two unrelated schedules, and both windows differ per machine.
Emit them from the loader and plot each series only inside its own; the reference
archive has 288 days of history against 134 of engagement on one machine, 427 against
230 on the other.

- **Absent is not zero.** A day before a machine's engagement window has no row at all.
  Emit `null`, not `0`, or a chart draws months of floor that never happened.
- **`visit_count` is not the number of visits.** Firefox excludes `RELOAD` and
  `DOWNLOAD` — 7.4% of rows here. Either number is defensible; say which one a figure
  is.
- **Nothing deduplicates across machines.** Page ids and guids are both profile-local
  (11093 shared ids, exactly one meaning the same URL), so identity is `(machine, URL)`.
  Pooling two profiles' bookmarks or view time reports a total the archive cannot
  support.
- **A missing referrer is not "typed directly".** It means no referrer, an expired
  referring visit, or a page since deleted — 29% of visits here, indistinguishably. The
  `TYPED` transition is the field that actually means typed.
- **`VisitSource.SEARCHED` marks the search page, not what came from it.** Every one of
  the 3647 lands on a search engine itself. Arrivals *from* a search have to come from
  referrers. The same flag also lands on a site's own in-page search, so detecting
  engines by it needs a share threshold — Wikipedia carries 2 such visits against
  thousands and would otherwise be treated as a search engine.
- **View time is foreground, non-idle time.** Not how long a tab was open, and upstream
  admits losing ~2s per idle transition. A floor on attention. 37 rows here exceed their
  own wall-clock span, so do not assume that bound.
- **Bookmark `dateAdded` is usually an import.** 1905 of 1911 share a timestamp to the
  second with another, 609 in one group. It records when the library was moved, not when
  anything was found.
- **One engagement row is one page view, and a long-lived tab makes several** — Firefox
  starts a fresh row after an hour without updates.
- `document_type` is `GENERIC` for every row; `MEDIA` is unexercised, not absent by
  finding.
- **`Download.destination` names the account.** Keep the basename, drop the path, before
  it reaches a page.
