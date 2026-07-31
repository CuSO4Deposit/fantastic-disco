# observable-cuso4d

Dashboards over [CPI](../CPI), built with
[Observable Framework](https://observablehq.com/framework/).

Separate from CPI on purpose. CPI is a library with no runtime dependencies, which
is what makes it cheap to import anywhere; this is one consumer of it, with its own
node toolchain and its own release rhythm.

## Running

Data loaders read archived exports through CPI, so point them at the archive:

```console
$ export CPI_PIPEPIPE_EXPORTS='~/archives/pipepipe/PipePipeData-*'
$ npm install
$ npm run dev     # preview on 127.0.0.1:3000
$ npm run build   # static site in dist/
```

`nix develop` (or `direnv allow`) provides node, uv and the venv. The loaders exit
non-zero when `CPI_PIPEPIPE_EXPORTS` is unset rather than emitting an empty dataset
that would render as "nothing watched".

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
