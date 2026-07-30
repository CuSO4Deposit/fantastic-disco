---
theme: dashboard
title: Video · Raw
---

# Video · Raw

Every row, no aggregation. Charts answer questions you already thought to ask; this
is for the ones you haven't.

```js
const raw = FileAttachment("./data/videos.json").json();
const searchesData = FileAttachment("./data/searches.json").json();
```

```js
const videos = raw.videos;
```

```js
// Flattened so the table can sort and filter on watch fields directly.
const rows = videos.map((d) => ({
  title: d.title,
  uploader: d.uploader,
  service: d.service,
  minutes: d.duration_s == null ? null : Math.round(d.duration_s / 60),
  watched: d.watched ? new Date(d.watched.last) : null,
  plays: d.watched?.repeats ?? null,
  progress: d.watched?.progress ?? null,
  sub: d.subscribed,
  playlists: d.playlists.join(", "),
  feed: d.feed_from,
  views: d.view_count,
  uploaded: d.uploaded ? new Date(d.uploaded) : null,
  url: d.url,
}));
```

```js
const query = view(
  Inputs.search(rows, {
    placeholder: "Search titles, uploaders, playlists…",
    columns: ["title", "uploader", "playlists", "feed", "service"],
  })
);
```

```js
const onlyUnwatched = view(Inputs.toggle({ label: "Only never played" }));
const service = view(
  Inputs.select([null, ...new Set(rows.map((d) => d.service))], {
    label: "Service",
    format: (d) => d ?? "any",
  })
);
```

```js
const filtered = query.filter(
  (d) =>
    (!onlyUnwatched || d.watched == null) && (service == null || d.service === service)
);
```

<div class="card">

${filtered.length.toLocaleString()} of ${rows.length.toLocaleString()} videos

```js
Inputs.table(filtered, {
  columns: [
    "title",
    "uploader",
    "service",
    "minutes",
    "watched",
    "plays",
    "progress",
    "sub",
    "playlists",
    "views",
    "uploaded",
  ],
  header: { sub: "subscribed", minutes: "length" },
  format: {
    progress: (p) => (p == null ? "" : `${(p * 100).toFixed(0)}%`),
    minutes: (m) => (m == null ? "live" : `${m}m`),
    watched: (d) => (d ? d.toISOString().slice(0, 10) : "never"),
    uploaded: (d) => (d ? d.toISOString().slice(0, 10) : ""),
    views: (v) => (v == null ? "" : v.toLocaleString()),
    title: (t, i, data) =>
      htl.html`<a href=${data[i].url} target="_blank" rel="noopener">${t}</a>`,
  },
  width: { title: 380, playlists: 140 },
  rows: 30,
  sort: "watched",
  reverse: true,
})
```

</div>

## Searches

```js
const searchQuery = view(
  Inputs.search(searchesData, { placeholder: "Search past searches…" })
);
```

<div class="card">

```js
Inputs.table(searchQuery, {
  columns: ["when", "query", "service"],
  format: { when: (d) => d.slice(0, 16).replace("T", " ") },
  width: { query: 400 },
  rows: 20,
  sort: "when",
  reverse: true,
})
```

</div>

## Raw JSON

The loaders' output is served as-is, so anything above can be pulled apart
elsewhere. Both files are built from the archive at build time and reflect the
denylist.

```js
// Built filenames are content-hashed, so the href has to come from the
// FileAttachment rather than being written out as a path.
display(
  htl.html`<p>
    <a href=${FileAttachment("./data/videos.json").href} download>videos.json</a>
    · ${(videos.length).toLocaleString()} rows<br>
    <a href=${FileAttachment("./data/searches.json").href} download>searches.json</a>
    · ${searchesData.length.toLocaleString()} rows
  </p>`
);
```
