---
theme: dashboard
title: Firefox · Library
---

# Firefox · Library

Bookmarks and downloads — what was kept rather than passed through. [Overview](./) is
the history; [Attention](./attention) is what pages held.

```js
const library = FileAttachment("./data/library.json").json();
```

```js
const bookmarks = library.bookmarks;
const downloads = library.downloads;
const folders = library.folders;

const neverOpened = bookmarks.filter((d) => d.visits === 0);
const machines = [...new Set(bookmarks.map((d) => d.machine))].sort();
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Bookmarks</h2>
    <span class="big">${bookmarks.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Folders</h2>
    <span class="big">${library.folder_rows.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Never opened</h2>
    <span class="big">${((100 * neverOpened.length) / bookmarks.length).toFixed(0)}%</span>
  </div>
  <div class="card">
    <h2>Downloads</h2>
    <span class="big">${downloads.length.toLocaleString()}</span>
  </div>
</div>

<div class="warning">

Bookmarks are present state, not a log. Deleting one removes its row, and without Sync
there is no tombstone anywhere — so this is what is bookmarked now, and no snapshot can
say what was bookmarked and later dropped. The counts are also per machine rather than
deduplicated: without Sync the same URL on two profiles is two independent records, and
${machines.length} machines here hold ${bookmarks.length.toLocaleString()} rows between
them.

</div>

## When they were added

```js
const added = Array.from(
  d3.rollup(bookmarks, (v) => v.length, (d) => d.added),
  ([date, count]) => ({ date: new Date(`${date}T00:00:00Z`), date_str: date, count })
).sort((a, b) => a.date - b.date);
```

```js
Plot.plot({
  title: "Bookmarks by the date they were added",
  subtitle: `${bookmarks.length.toLocaleString()} bookmarks across ${added.length} distinct days`,
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Bookmarks added", grid: true },
  marks: [
    Plot.barY(added, { x: "date", y: "count", fill: "var(--theme-foreground-focus)", tip: true, channels: { day: "date_str" } }),
    Plot.ruleY([0]),
  ],
})
```

```js
// Bursts of bookmarks sharing one second, which is the signature of an import rather
// than of browsing. Read off the full timestamp; the date alone hides it.
const bursts = Array.from(
  d3.rollup(bookmarks, (v) => v.length, (d) => d.added_at.slice(0, 19)),
  ([second, count]) => ({ second, count })
)
  .filter((d) => d.count > 1)
  .sort((a, b) => b.count - a.count);
const inBursts = d3.sum(bursts, (d) => d.count);
```

```js
display(
  htl.html`<p><b>${inBursts.toLocaleString()}</b> of
    ${bookmarks.length.toLocaleString()} bookmarks share their timestamp to the second
    with at least one other, the largest such group being
    <b>${bursts[0].count.toLocaleString()}</b> at once. So <code>dateAdded</code> here is
    mostly not when something was found — an import or a profile restore stamps every row
    it writes with the time of the import. Treat the chart above as a record of when the
    library was moved, and only the small counts as when things were actually
    bookmarked.</p>`
);
```

## How they are filed

```js
// Faceted by machine, not coloured by it: the same folder name exists on both machines
// — ten of the twenty largest are duplicated — and a shared `y` band would draw the two
// bars over each other, showing one machine's count and hiding the other's.
const machineFolders = machines.map((machine) => ({
  machine,
  rows: folders.filter((d) => d.machine === machine).slice(0, 12),
}));
```

```js
for (const { machine, rows } of machineFolders) {
  display(
    Plot.plot({
      title: `Bookmarks per folder · ${machine}`,
      subtitle:
        machine === machines[0]
          ? "Firefox's own root names — unfiled is the “other bookmarks” bucket. Twelve largest per machine."
          : undefined,
      width,
      height: 60 + rows.length * 26,
      marginLeft: 220,
      x: { label: "Bookmarks", grid: true, domain: [0, d3.max(folders, (d) => d.bookmarks)] },
      y: { label: null },
      marks: [
        Plot.barX(rows, {
          x: "bookmarks",
          y: "folder",
          fill: "var(--theme-foreground-focus)",
          sort: { y: "x", reverse: true },
          tip: true,
        }),
        Plot.ruleX([0]),
      ],
    })
  );
}
```

```js
const roots = Array.from(
  d3.rollup(bookmarks, (v) => v.length, (d) => d.root ?? "(none)"),
  ([root, count]) => ({ root, count })
).sort((a, b) => b.count - a.count);
```

```js
display(
  htl.html`<p>${roots
    .map((r, i) => htl.html`${i ? ", " : ""}<b>${r.count.toLocaleString()}</b> under <code>${r.root}</code>`)}.
    These are Firefox's internal root names rather than the localized labels the UI
    shows: <code>unfiled</code> is "Other bookmarks", <code>toolbar</code> is the
    bookmarks bar.</p>`
);
```

## Saved and never opened

```js
Plot.plot({
  title: "Bookmarks by how often the page was visited",
  subtitle: `${neverOpened.length.toLocaleString()} of ${bookmarks.length.toLocaleString()} bookmarked pages have no visit at all on the machine that holds them`,
  width,
  height: 260,
  x: { label: "Visits to the bookmarked page →", domain: [0, 20] },
  y: { label: "Bookmarks", grid: true },
  marks: [
    Plot.rectY(bookmarks, Plot.binX({ y: "count" }, { x: "visits", thresholds: d3.range(0, 21), fill: "var(--theme-foreground-focus)" })),
    Plot.ruleY([0]),
  ],
})
```

```js
display(
  htl.html`<p>Visits here are Firefox's own <code>visit_count</code>, which excludes
    reloads and downloads and restarts from zero if the page was expired from history and
    later visited again. So a zero is "no visit the browser currently remembers", not
    proof the link was never opened. Bookmarks capped at 20 visits in the chart; the
    tail runs further.</p>`
);
```

```js
const bySite = Array.from(
  d3.rollup(neverOpened, (v) => v.length, (d) => d.site),
  ([site, count]) => ({ site, count })
)
  .sort((a, b) => b.count - a.count)
  .slice(0, 15);
```

```js
Plot.plot({
  title: "Sites bookmarked but not visited",
  subtitle: "where the unread bookmarks point",
  width,
  height: 400,
  marginLeft: 190,
  x: { label: "Bookmarks never opened", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(bySite, { x: "count", y: "site", fill: "var(--theme-foreground-focus)", sort: { y: "x", reverse: true }, tip: true }),
    Plot.ruleX([0]),
  ],
})
```

## Downloads

```js
const byExt = Array.from(
  d3.rollup(downloads, (v) => v.length, (d) => d.extension),
  ([extension, count]) => ({ extension, count })
).sort((a, b) => b.count - a.count);
const sized = downloads.filter((d) => d.bytes != null);
const totalBytes = d3.sum(sized, (d) => d.bytes);
```

<div class="grid grid-cols-3">
  <div class="card">
    <h2>Downloads recorded</h2>
    <span class="big">${downloads.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Total size</h2>
    <span class="big">${(totalBytes / 1e9).toFixed(1)} GB</span>
  </div>
  <div class="card">
    <h2>Still on disk</h2>
    <span class="big">${downloads.filter((d) => d.deleted === false).length.toLocaleString()}</span>
  </div>
</div>

<div class="warning">

Firefox has no download table. These are reconstructed from two annotations on the
source page, keyed per page — so downloading the same URL twice **overwrites** the
earlier record, and only the most recent survives in any snapshot. The
${downloads.length.toLocaleString()} rows here are a floor, and accumulating more
snapshots is the only thing that recovers the difference.

</div>

```js
Plot.plot({
  title: "Downloads by file type",
  subtitle: `${downloads.length.toLocaleString()} records across ${byExt.length} extensions`,
  width,
  height: 380,
  marginLeft: 110,
  x: { label: "Downloads", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(byExt, { x: "count", y: "extension", fill: "var(--theme-foreground-focus)", sort: { y: "x", reverse: true }, tip: true }),
    Plot.ruleX([0]),
  ],
})
```

```js
Plot.plot({
  title: "Download sizes",
  subtitle: `${sized.length} of ${downloads.length.toLocaleString()} records carry a file size. Log-spaced bins: the range runs from a few kilobytes to a few gigabytes.`,
  width,
  height: 260,
  x: {
    label: "Bytes →",
    type: "log",
    tickFormat: (d) => (d >= 1e9 ? `${d / 1e9}G` : d >= 1e6 ? `${d / 1e6}M` : d >= 1e3 ? `${d / 1e3}k` : d),
  },
  y: { label: "Downloads", grid: true },
  marks: [
    Plot.rectY(sized, Plot.binX({ y: "count" }, {
      x: "bytes",
      // Explicit log-spaced thresholds. `thresholds: n` bins linearly, which on a log
      // axis puts everything below a gigabyte in one bar.
      thresholds: d3.range(3, 10.5, 0.5).map((e) => 10 ** e),
      fill: "var(--theme-foreground-focus)",
    })),
    Plot.ruleY([0]),
  ],
})
```

```js
const dlDays = Array.from(
  d3.rollup(downloads, (v) => v.length, (d) => d.added),
  ([date, count]) => ({ date: new Date(`${date}T00:00:00Z`), count })
).sort((a, b) => a.date - b.date);
```

```js
Plot.plot({
  title: "Downloads over time",
  subtitle: "by the date the annotation was written, which is when the download finished",
  width,
  height: 220,
  x: { label: null, type: "utc" },
  y: { label: "Downloads", grid: true },
  marks: [
    Plot.barY(dlDays, { x: "date", y: "count", fill: "var(--theme-foreground-focus)", tip: true }),
    Plot.ruleY([0]),
  ],
})
```

<div class="card">

```js
Inputs.table(
  downloads.map((d) => ({
    filename: d.filename,
    site: d.site,
    size: d.bytes,
    added: d.added,
    machine: d.machine,
    "on disk": d.deleted == null ? "unknown" : d.deleted ? "deleted" : "yes",
  })),
  {
    format: { size: (b) => (b == null ? "" : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e3).toFixed(0)} kB`) },
    width: { filename: 300 },
    rows: 20,
    sort: "added",
    reverse: true,
  }
)
```

</div>

<div class="note">

Only the filename is shown, never the path it was saved to. Firefox records the full
`file://` destination, which on any real machine contains the account name — so the
loader keeps the basename and drops the rest before it reaches this page.

</div>
