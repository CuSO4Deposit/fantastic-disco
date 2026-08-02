# observable-cuso4d

Dashboards over [CPI](../CPI), built with
[Observable Framework](https://observablehq.com/framework/).

Separate from CPI on purpose. CPI is a library with no runtime dependencies, which
is what makes it cheap to import anywhere; this is one consumer of it, with its own
node toolchain and its own release rhythm.

## Running

Data loaders read archived exports through CPI, so point them at the archive:

```console
$ export CPI_PIPEPIPE_EXPORTS='~/archives/redmi50/app/*.NewPipeEnhanced/PipePipeData-*.zip'
$ export CPI_LOCAL_TZ=Europe/Paris
$ npm install
$ npm run dev     # preview on 127.0.0.1:3000
$ npm run build   # static site in dist/
```

That builds the video pages alone. `nix develop` (or `direnv allow`) provides node, uv
and the venv.

## Environment

Every variable the site reads, in one place. Only the first is needed to build
anything; each source below it is optional, and a source whose variable is unset is
dropped from the site rather than published empty.

| Variable | Needed for | Notes |
| --- | --- | --- |
| `CPI_PIPEPIPE_EXPORTS` | **required** | Glob of PipePipe export zips. The one source the build refuses to go without. |
| `CPI_LOCAL_TZ` | required by every source except video | IANA zone the data was recorded in, e.g. `Asia/Tokyo`. No default on purpose. |
| `CPI_GADGETBRIDGE_EXPORTS` | Band pages | Glob of Gadgetbridge backup zips. |
| `CPI_FIREFOX_EXPORTS` | Firefox pages | Glob of archived `places-<host>-<stamp>.sqlite.xz`. Must span machines — see below. |
| `YOFFLINE_DB` | Rhythm pages | Path to `y_offline.db`. A live database, not an archived export. |
| `YOFFLINE_USER` | Rhythm pages | Whose records to read. Every table is keyed `(time, user)`. |
| `ARCSONG_DB` | Arcaea | `arcsong.db` from ArcaeaSongDatabase. |
| `PJSK_MUSICS_JSON` | Project SEKAI | `musics.json` from sekai-master-db-diff. |
| `PJSK_DIFFICULTIES_JSON` | Project SEKAI | `musicDifficulties.json`, alongside the above. |
| `CYTUS2_CHARTS_JSON` | Cytus II | A hand-maintained `charts.json`. |

Three things worth knowing beyond the table.

**Loaders exit non-zero rather than emitting nothing.** A variable pointing at an empty
glob stops the build. The alternative is worse than a failure: an empty dataset renders
as a plausible "nothing watched", "never wore the band" or "never played".

**`CPI_LOCAL_TZ` has no default, and that is deliberate.** It decides which local
midnight splits a day, and a wrong boundary does not look wrong — every daily total
stays a perfectly plausible number, just cut in the wrong place. The build refuses when
a source needs it and it is unset rather than falling back to the machine's zone, which
on the server is UTC.

**`CPI_FIREFOX_EXPORTS` must match every machine's snapshots.** Firefox is the one
source that genuinely runs on several, and page ids are profile-local, so identity is
`(machine, URL)` and the host is read out of each filename. A glob naming one device
publishes that laptop's browsing as though it were the whole record — a complete-looking
site quietly missing half its history. `'/data/*/firefox/places-*.sqlite.xz'` rather
than `/data/lexikos/...`.

At least one rhythm catalogue must be configured if `src/rhythm/` is present; the
loaders refuse otherwise, since Y-Offline cannot rate a play without one and "no
catalogue" would render identically to "never played".

## Privacy

`dist/` and `src/.observablehq/` hold actual watch history, so both are gitignored.
Only loader source and page markup are tracked. Anything published from `dist/` is
a full copy of the underlying data — there is no aggregation happening server-side,
since there is no server.

## Layout

    src/index.md              landing page
    src/lib/_shared.py        export location and denylist, shared by all sources
    src/video/index.md        overview
    src/video/fandoms.md      the same watching, split by what I follow
    src/video/raw.md          every row, searchable, plus raw JSON downloads
    src/video/data/*.json.py  loaders; import cuso4d.* and print JSON to stdout
    src/band/                 the same shape over Gadgetbridge
    src/firefox/              and over archived places.sqlite snapshots
    src/rhythm/               and over Y-Offline, which is a live database rather
                              than an archive — see Environment

One directory per source, so each keeps its pages and loaders together and a second
source can be added without disturbing this one. Pages nest as sections, hence
`/video/fandoms` rather than a top-level `/fandoms` — both are views of the same
watch data, not peers of it.

Adding a chart is usually a JS block in the Markdown. Adding a *field* means
editing the matching loader, since only what a loader emits reaches the browser.

## Hiding uploaders

Copy `src/lib/blocked.example.txt` to `src/lib/blocked.txt` (gitignored) and list
uploader names, one per line, matched exactly:

```
Some Channel Name
```

Filtering happens in the loader, never in CPI: the library's job is to report what
the archive says, and the archive keeps everything. Removing a name brings those
videos straight back. Pages state how many rows were withheld rather than showing
totals that quietly disagree with the data.

Editing the list takes effect on the next `npm run dev` or `npm run build`. A
`prebuild`/`predev` step handles that, because Framework decides a loader's cached
output is fresh by comparing mtimes with the loader script alone and never sees the
denylist — without it, the page would keep showing the uploaders you just excluded.
Restarting the dev server picks up changes; editing the file while it runs does not.

Adding a chart is usually a JS block in the Markdown. Adding a *field* means
editing the matching loader, since only what a loader emits reaches the browser.

## What the charts can and cannot say

PipePipe stores one history row per video and overwrites its timestamp on every
play, so an export knows only when each video was last watched. Consequences the
page is built around:

- Time spent is shown as a range. Counting each video once is a floor; weighting by
  the app's play counter is a ceiling far above the truth, since that counter
  increments on replays, seeks and background loops.
- There are no per-day or per-week charts. With a single snapshot they would
  compress years of viewing onto scattered points and read as near-zero activity.
  Those become meaningful once several exports have accumulated.
- Live streams have no duration, so they are excluded from length and total-time
  charts rather than counted as zero.

Firefox is the opposite in one way and worse in another. Visit rows are immutable, so
one snapshot holds a real timeline and per-day charts are sound — but Firefox deletes
its own rows, and on two different schedules:

- History expires when the database outgrows its size limit, on no schedule the file
  records. The left end of every series is where expiration last cut, not where the
  browsing began.
- Engagement rows are expired on age, much sooner than the visits they describe: 134
  days against 288 on one machine here, 230 against 427 on the other. View time is
  therefore absent, not zero, before a date that differs per machine — the pages plot
  it only inside each machine's own window and say so.
- Reading time is foreground, non-idle time only, so it is a floor on attention rather
  than how long a tab was open.
- Bookmarks are present state with no tombstones, and their `dateAdded` is usually the
  time of an import rather than when anything was found.
- Downloads are reconstructed from per-page annotations, so re-downloading a URL
  overwrites the earlier record; the count is a floor.
- Nothing is deduplicated across machines. Page ids and guids are both profile-local,
  so identity is `(machine, URL)` and the same page on two profiles is two records.
