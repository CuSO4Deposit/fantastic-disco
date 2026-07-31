---
theme: dashboard
title: Video
---

# Video

Watch history, searches and subscriptions from PipePipe.
[Fandoms](./fandoms) splits this by what I follow; [Raw](./raw) is every row.

```js
const raw = FileAttachment("./data/videos.json").json();
const searches = FileAttachment("./data/searches.json").json();
```

```js
const videos = raw.videos;
const excluded = raw.excluded;
const watched = videos.filter((d) => d.watched);
const unwatched = videos.filter((d) => !d.watched);

// Lower bound on time spent: each video counted once, live streams excluded since
// their duration is unknown. Weighting by repeat count would be far too loose —
// replays, seeks and background loops all increment it.
const hoursOnce = d3.sum(watched, (d) => d.duration_s ?? 0) / 3600;
const hoursRepeats =
  d3.sum(watched, (d) => (d.duration_s ?? 0) * Math.max(d.watched.repeats, 1)) / 3600;
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Videos known</h2>
    <span class="big">${videos.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Watched</h2>
    <span class="big">${watched.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Never played</h2>
    <span class="big">${unwatched.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Hours, at least</h2>
    <span class="big">${hoursOnce.toLocaleString(undefined, {maximumFractionDigits: 0})}</span>
  </div>
</div>

<div class="note">

Time spent is a range, not a number: **${hoursOnce.toFixed(0)}h** counting each
video once, up to **${hoursRepeats.toFixed(0)}h** if every repeat were a full
viewing. The truth sits near the low end — see the rewatch table below for why.

</div>

```js
// A JS block rather than an inline ${...}: an inline expression spanning blank
// lines ends the Markdown paragraph, and the rest renders as literal source.
if (excluded > 0) {
  display(
    htl.html`<div class="warning">
      ${excluded.toLocaleString()} videos are held back by the uploader denylist,
      so every count on this page is short by that much. The archive itself is
      complete.
    </div>`
  );
}
```

## What got finished

```js
const withProgress = watched.filter((d) => d.watched.progress != null);
```

```js
Plot.plot({
  title: "Playback progress when last watched",
  subtitle: `${withProgress.length.toLocaleString()} videos with a stored position`,
  width,
  height: 220,
  x: { label: "Progress →", percent: true, domain: [0, 100] },
  y: { label: "Videos", grid: true },
  marks: [
    Plot.rectY(
      withProgress,
      Plot.binX({ y: "count" }, { x: (d) => d.watched.progress, thresholds: 50, fill: "var(--theme-foreground-focus)" })
    ),
    Plot.ruleY([0]),
  ],
})
```

One peak, heavy tail: **${(100 * withProgress.filter((d) => d.watched.progress > 0.99).length / withProgress.length).toFixed(0)}%**
of videos with a stored position were watched essentially to the end, and the rest
spread thinly across every level of abandonment rather than clustering at the
bottom. Note that a position at exactly 100% is mostly the player rounding up.

## Where the attention goes

```js
Plot.plot({
  title: "Most-watched uploaders",
  width,
  height: 320,
  marginLeft: 160,
  x: { label: "Videos watched", grid: true },
  y: { label: null },
  color: { legend: true, domain: [true, false], range: ["var(--theme-foreground-focus)", "#888"], tickFormat: (d) => (d ? "subscribed" : "not subscribed") },
  marks: [
    Plot.barX(
      d3
        .rollups(watched, (v) => ({ n: v.length, sub: v[0].subscribed }), (d) => d.uploader)
        .map(([uploader, { n, sub }]) => ({ uploader, n, sub }))
        .sort((a, b) => b.n - a.n)
        .slice(0, 12),
      { x: "n", y: "uploader", fill: "sub", sort: { y: "x", reverse: true } }
    ),
    Plot.ruleX([0]),
  ],
})
```

```js
const lengths = watched.filter((d) => d.duration_s > 0).map((d) => d.duration_s / 60);
// Explicit log-spaced thresholds. A plain `thresholds: 40` bins linearly, which on
// a log axis puts 88% of these videos in one bar spanning most of the width.
const lengthBins = d3.range(0, 25).map((i) => 0.25 * 2 ** (i / 2));
```

```js
Plot.plot({
  title: "Video length",
  subtitle: `${lengths.length.toLocaleString()} videos; median ${d3.median(lengths).toFixed(1)} min. Live streams excluded, their duration is unknown.`,
  width,
  height: 320,
  x: {
    label: "Minutes →",
    type: "log",
    domain: [0.25, d3.max(lengths)],
    ticks: [0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
    tickFormat: (d) => (d < 1 ? `${d * 60}s` : d < 60 ? `${d}m` : `${d / 60}h`),
  },
  y: { label: "Videos", grid: true },
  marks: [
    Plot.rectY(
      lengths,
      Plot.binX({ y: "count" }, { x: (d) => d, thresholds: lengthBins, fill: "var(--theme-foreground-focus)" })
    ),
    Plot.ruleY([0]),
  ],
})
```

## How current is any of this

```js
// Only exact upload dates: PipePipe derives some from relative strings like
// "3 days ago", which would smear this chart.
const lags = watched
  .filter((d) => d.uploaded && !d.uploaded_is_approximate)
  .map((d) => ({
    ...d,
    days: (new Date(d.watched.last) - new Date(d.uploaded)) / 86400000,
  }))
  .filter((d) => d.days >= 0);
```

```js
// Same reason as the length chart: linear bins on a log axis would put 56% of these
// in one bar and hide the two humps entirely.
const lagDays = lags.map((d) => Math.max(d.days, 0.5));
const lagBins = d3.range(0, 29).map((i) => 0.5 * 2 ** (i / 2));
```

```js
Plot.plot({
  title: "Delay between a video going up and me watching it",
  subtitle: `median ${d3.median(lagDays).toFixed(0)} days, mean ${d3.mean(lagDays).toFixed(0)} — the gap is the backlog`,
  width,
  height: 240,
  x: {
    label: "Time after upload →",
    type: "log",
    domain: [0.5, d3.max(lagDays)],
    ticks: [1, 7, 30, 90, 365, 1095, 3650],
    tickFormat: (d) => (d < 30 ? `${d}d` : d < 365 ? `${Math.round(d / 30)}mo` : `${Math.round(d / 365)}y`),
  },
  y: { label: "Videos", grid: true },
  marks: [
    Plot.rectY(lagDays, Plot.binX({ y: "count" }, { x: (d) => d, thresholds: lagBins, fill: "var(--theme-foreground-focus)" })),
    Plot.ruleY([0]),
  ],
})
```

Two distinct habits, not one: a spike inside the first two days for keeping up, and
a second hump around four to eight years back where old material gets dug up. The
median sits at ${d3.median(lagDays).toFixed(0)} days, in the quiet valley between
them, which is why the mean is seven times larger.

## Saved and never played

```js
const reachedBy = (d) =>
  d.playlists.length ? "in a playlist" : d.feed_from ? "from a feed" : "neither";
```

```js
Plot.plot({
  title: "How the never-played were reached",
  width,
  height: 200,
  marginLeft: 100,
  x: { label: "Videos", grid: true },
  y: { label: null },
  color: { legend: true },
  marks: [
    Plot.barX(unwatched, Plot.groupY({ x: "count" }, { y: reachedBy, fill: "service", sort: { y: "x", reverse: true } })),
    Plot.ruleX([0]),
  ],
})
```

```js
Plot.plot({
  title: "Uploaders whose videos pile up unwatched",
  width,
  height: 200,
  marginLeft: 160,
  x: { label: "Never played", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(
      d3
        .rollups(unwatched, (v) => v.length, (d) => d.uploader)
        .map(([uploader, n]) => ({ uploader, n }))
        .sort((a, b) => b.n - a.n)
        .slice(0, 8),
      { x: "n", y: "uploader", fill: "#888", sort: { y: "x", reverse: true } }
    ),
    Plot.ruleX([0]),
  ],
})
```

## What the feed actually converts

```js
const feedShown = videos.filter((d) => d.feed_from);
const feedWatched = feedShown.filter((d) => d.watched);
const perSub = d3
  .rollups(
    feedShown,
    (v) => ({ shown: v.length, watched: v.filter((d) => d.watched).length }),
    (d) => d.feed_from
  )
  .map(([name, v]) => ({ name, ...v, rate: v.watched / v.shown }))
  .filter((d) => d.shown >= 5)
  .sort((a, b) => a.rate - b.rate);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Videos the feed showed</h2>
    <span class="big">${feedShown.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Of those, played</h2>
    <span class="big">${feedWatched.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Conversion</h2>
    <span class="big">${(100 * feedWatched.length / feedShown.length).toFixed(0)}%</span>
  </div>
  <div class="card">
    <h2>Subs never converting</h2>
    <span class="big">${perSub.filter((d) => d.watched === 0).length}</span>
  </div>
</div>

```js
Plot.plot({
  title: "Feed conversion by subscription",
  subtitle: "channels with at least 5 videos in the feed window",
  width,
  height: 30 + perSub.length * 20,
  marginLeft: 200,
  x: { label: "Videos shown in feed →", grid: true },
  y: { label: null, domain: perSub.map((d) => d.name) },
  color: { legend: true, domain: ["played", "skipped"], range: ["var(--theme-foreground-focus)", "#666"] },
  marks: [
    Plot.barX(perSub, { x: "shown", y: "name", fill: "#666" }),
    Plot.barX(perSub, { x: "watched", y: "name", fill: "var(--theme-foreground-focus)" }),
    Plot.text(perSub, { x: "shown", y: "name", text: (d) => ` ${(100 * d.rate).toFixed(0)}%`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

The feed is mostly not how videos get watched here. Subscribing and watching turn
out to be close to separate activities — see the searching section for what does
lead to a play.

## Playlists as intent

```js
const playlistStats = d3
  .rollups(
    videos.filter((d) => d.playlists.length),
    (v) => ({ total: v.length, watched: v.filter((d) => d.watched).length }),
    (d) => d.playlists[0]
  )
  .map(([name, v]) => ({ name, ...v, rate: v.watched / v.total }))
  .sort((a, b) => b.total - a.total);
```

```js
Plot.plot({
  title: "How much of each playlist got watched",
  width,
  height: 30 + playlistStats.length * 24,
  marginLeft: 140,
  x: { label: "Videos →", grid: true },
  y: { label: null, domain: playlistStats.map((d) => d.name) },
  marks: [
    Plot.barX(playlistStats, { x: "total", y: "name", fill: "#666" }),
    Plot.barX(playlistStats, { x: "watched", y: "name", fill: "var(--theme-foreground-focus)" }),
    Plot.text(playlistStats, { x: "total", y: "name", text: (d) => ` ${(100 * d.rate).toFixed(0)}%`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

These are near-fully watched, which makes them look less like a queue of things to
get to and more like a record of what was already seen.

## Returned to most

```js
Inputs.table(
  watched
    .filter((d) => d.watched.repeats > 1)
    .sort((a, b) => b.watched.repeats - a.watched.repeats)
    .slice(0, 15),
  {
    columns: ["watched", "title", "uploader", "duration_s", "service"],
    header: { watched: "Plays", duration_s: "Length" },
    format: {
      watched: (w) => w.repeats.toLocaleString(),
      duration_s: (s) => (s == null ? "live" : `${Math.round(s / 60)}m`),
      title: (t) => t.slice(0, 60),
    },
    width: { title: 400 },
  }
)
```

A play here is whatever the app counted as one, so replays, seeks and background
loops are all folded in. Useful for ranking what pulled me back; useless as a
duration.

```js
// Abandoned early yet returned to repeatedly — the two signals disagree, which is
// what makes these interesting: background audio, or a reference kept reopening.
const paradox = watched
  .filter((d) => d.watched.progress != null && d.watched.progress < 0.1 && d.watched.repeats >= 3)
  .sort((a, b) => b.watched.repeats - a.watched.repeats);
```

<div class="card">
  <h2>Opened often, watched barely — ${paradox.length} videos</h2>

```js
Inputs.table(paradox.slice(0, 10), {
  columns: ["watched", "title", "uploader", "duration_s"],
  header: { watched: "Plays / progress", duration_s: "Length" },
  format: {
    watched: (w) => `${w.repeats} · ${(w.progress * 100).toFixed(0)}%`,
    duration_s: (s) => (s == null ? "live" : `${Math.round(s / 60)}m`),
    title: (t) => t.slice(0, 55),
  },
  width: { title: 380 },
})
```

Long streams dominate here, which fits: a three-hour karaoke archive opened 38 times
and never scrubbed past the start is something playing in the background, not
something being watched.

</div>

## Language

```js
const lang = (t) =>
  /[぀-ヿ]/.test(t) ? "Japanese" : /[一-鿿]/.test(t) ? "Chinese" : "Other";
```

```js
Plot.plot({
  title: "Title script of videos watched",
  subtitle: "a rough proxy: Japanese detected by kana, so kanji-only titles read as Chinese",
  width,
  height: 120,
  marginLeft: 90,
  x: { label: "Videos", grid: true },
  y: { label: null },
  color: { legend: true },
  marks: [
    Plot.barX(watched, Plot.groupY({ x: "count" }, { y: lang, fill: "service", sort: { y: "x", reverse: true } })),
    Plot.ruleX([0]),
  ],
})
```

## Searching

```js
const distinctQueries = new Set(searches.map((d) => d.query)).size;
// A bare BV id is a pasted link rather than a search. Only bilibili's ids are
// detectable: a YouTube id is 11 characters of [\w-], which also describes plenty
// of ordinary queries — "speculation" and "さくら荘のペットな彼女" both match, so
// that rule would inflate this considerably.
const isId = (q) => /^BV[0-9A-Za-z]{10}$/.test(q);
const pasted = searches.filter((d) => isId(d.query));
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Searches</h2>
    <span class="big">${searches.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Distinct</h2>
    <span class="big">${distinctQueries.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Pasted video ids</h2>
    <span class="big">${(100 * pasted.length / searches.length).toFixed(0)}%</span>
  </div>
  <div class="card">
    <h2>Actual queries</h2>
    <span class="big">${(searches.length - pasted.length).toLocaleString()}</span>
  </div>
</div>

<div class="note">

Most of the search box's traffic isn't searching. **${pasted.length.toLocaleString()}**
of ${searches.length.toLocaleString()} entries are a bare bilibili id pasted in,
meaning the decision to watch was already made elsewhere and the app was only the
player. That leaves ${(searches.length - pasted.length).toLocaleString()} entries as
someone actually looking for something — and it's an undercount, since a pasted
YouTube id is indistinguishable from a short query.

</div>

```js
Plot.plot({
  title: "Query length, real searches only",
  subtitle: "pasted ids excluded",
  width,
  height: 200,
  x: { label: "Characters →" },
  y: { label: "Searches", grid: true },
  marks: [
    Plot.rectY(
      searches.filter((d) => !isId(d.query)),
      Plot.binX({ y: "count" }, { x: (d) => d.query.length, thresholds: 25, fill: "var(--theme-foreground-focus)" })
    ),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Searches by service",
  width,
  height: 140,
  marginLeft: 80,
  x: { label: "Searches", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(searches, Plot.groupY({ x: "count" }, { y: "service", sort: { y: "x", reverse: true } })),
    Plot.ruleX([0]),
  ],
})
```
