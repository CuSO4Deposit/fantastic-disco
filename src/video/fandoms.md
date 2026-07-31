---
theme: dashboard
title: Video · Fandoms
---

# Video · Fandoms

How I watch the two things I follow, next to everything else. Nothing here is about
those communities themselves — only about my own consumption of them.

```js
const raw = FileAttachment("./data/videos.json").json();
const searchData = FileAttachment("./data/searches.json").json();
```

```js
const videos = raw.videos;
const watched = videos.filter((d) => d.watched);
// From the loader, not written out here: the group names are local configuration,
// and spelling them out in a page would put them back into the repo.
const names = raw.groups;
const groups = [...names, "Everything else"];

// A video with no tag is "everything else"; one matching several goes to its first
// tag so the groups stay disjoint and shares add to 100%.
const groupOf = (d) => (d.fandoms.length ? d.fandoms[0] : "Everything else");
const colour = {
  domain: groups,
  range: [...d3.schemeTableau10.slice(0, names.length), "#666"],
};
const hours = (rows) => d3.sum(rows, (d) => d.duration_s ?? 0) / 3600;
```

<div class="note">

Matching is by keyword against title and uploader, so it only finds videos that
*say* the name. Anything titled with just a song name goes uncounted, which makes
every number below a floor rather than a total.

</div>

<div class="grid grid-cols-3">${groups.map((g) => {
  const rows = watched.filter((d) => groupOf(d) === g);
  return htl.html`<div class="card">
    <h2>${g}</h2>
    <span class="big">${rows.length.toLocaleString()}</span>
    <p>${(100 * rows.length / watched.length).toFixed(0)}% of videos watched ·
       ${hours(rows).toFixed(0)}h at minimum</p>
  </div>`;
})}</div>

## Do I actually finish them

```js
const withProgress = watched.filter((d) => d.watched.progress != null);
```

```js
Plot.plot({
  title: "Playback progress, by what I was watching",
  subtitle: "each row normalised, so the shapes are comparable",
  width,
  height: 260,
  // `percent` is a scale transform: it multiplies by 100 before the scale sees the
  // value, so the domain belongs in percent space. [0, 1] would show the first 1%.
  // Bin thresholds stay in 0..1, since mark transforms run first.
  x: { label: "Progress →", percent: true, domain: [0, 100] },
  y: { label: null },
  color: colour,
  fy: { domain: groups, label: null },
  marks: [
    Plot.rectY(
      withProgress,
      Plot.binX(
        { y: "proportion-facet" },
        { x: (d) => d.watched.progress, fy: groupOf, fill: groupOf, thresholds: 20 }
      )
    ),
    Plot.ruleY([0]),
  ],
})
```

```js
const finishRates = groups.map((g) => {
  const rows = withProgress.filter((d) => groupOf(d) === g);
  return { group: g, rate: rows.filter((d) => d.watched.progress > 0.9).length / rows.length, n: rows.length };
});
```

```js
Plot.plot({
  title: "Share watched past 90%",
  width,
  height: 150,
  marginLeft: 120,
  x: { label: "Finished →", percent: true, domain: [0, 100], grid: true },
  y: { label: null, domain: groups },
  color: colour,
  marks: [
    Plot.barX(finishRates, { x: "rate", y: "group", fill: "group" }),
    Plot.text(finishRates, { x: "rate", y: "group", text: (d) => ` ${(100 * d.rate).toFixed(0)}%`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

## How long the things I watch are

```js
const lengths = watched.filter((d) => d.duration_s > 0);
const lengthBins = d3.range(0, 25).map((i) => 0.25 * 2 ** (i / 2));
```

```js
Plot.plot({
  title: "Video length by group",
  subtitle: "log-spaced bins; live streams excluded, their duration is unknown",
  width,
  height: 300,
  x: {
    label: "Length →",
    type: "log",
    domain: [0.25, d3.max(lengths, (d) => d.duration_s / 60)],
    ticks: [0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
    tickFormat: (d) => (d < 1 ? `${d * 60}s` : d < 60 ? `${d}m` : `${d / 60}h`),
  },
  y: { label: null },
  color: colour,
  fy: { domain: groups, label: null },
  marks: [
    Plot.rectY(
      lengths,
      Plot.binX(
        { y: "proportion-facet" },
        { x: (d) => d.duration_s / 60, fy: groupOf, fill: groupOf, thresholds: lengthBins }
      )
    ),
    Plot.ruleY([0]),
  ],
})
```

## Do I keep up, or catch up

```js
const lags = watched
  .filter((d) => d.uploaded && !d.uploaded_is_approximate)
  .map((d) => ({ ...d, days: Math.max((new Date(d.watched.last) - new Date(d.uploaded)) / 86400000, 0.5) }))
  .filter((d) => d.days >= 0.5);
const lagBins = d3.range(0, 29).map((i) => 0.5 * 2 ** (i / 2));
```

```js
Plot.plot({
  title: "Delay between upload and watching, by group",
  width,
  height: 300,
  x: {
    label: "Time after upload →",
    type: "log",
    domain: [0.5, d3.max(lags, (d) => d.days)],
    ticks: [1, 7, 30, 90, 365, 1095, 3650],
    tickFormat: (d) => (d < 30 ? `${d}d` : d < 365 ? `${Math.round(d / 30)}mo` : `${Math.round(d / 365)}y`),
  },
  y: { label: null },
  color: colour,
  fy: { domain: groups, label: null },
  marks: [
    Plot.rectY(lags, Plot.binX({ y: "proportion-facet" }, { x: (d) => d.days, fy: groupOf, fill: groupOf, thresholds: lagBins })),
    Plot.ruleY([0]),
  ],
})
```

```js
const medians = groups.map((g) => ({
  group: g,
  median: d3.median(lags.filter((d) => groupOf(d) === g), (d) => d.days),
}));
display(
  htl.html`<p>${medians.map((d) => htl.html`<strong>${d.group}</strong>: median ${d.median.toFixed(0)} days. `)}</p>`
);
```

The overall picture had two humps — keeping up, and digging through old material.
Splitting it by group puts each habit somewhere specific, and it comes out the
opposite way round from what "following something" suggests: everything else is what
gets watched fresh, while the followed things are mostly archive.

## Backlog and returns

```js
const summary = groups.map((g) => {
  const all = videos.filter((d) => groupOf(d) === g);
  const seen = all.filter((d) => d.watched);
  const repeats = seen.filter((d) => d.watched.repeats > 1);
  return {
    group: g,
    known: all.length,
    unwatched: all.length - seen.length,
    unwatchedShare: (all.length - seen.length) / all.length,
    rewatchShare: repeats.length / seen.length,
  };
});
```

<div class="grid grid-cols-2">
  <div class="card">

```js
Plot.plot({
  title: "Never played",
  subtitle: "share of everything known in that group",
  width,
  height: 150,
  marginLeft: 120,
  x: { label: "Never played →", percent: true, domain: [0, 100], grid: true },
  y: { label: null, domain: groups },
  color: colour,
  marks: [
    Plot.barX(summary, { x: "unwatchedShare", y: "group", fill: "group" }),
    Plot.text(summary, { x: "unwatchedShare", y: "group", text: (d) => ` ${d.unwatched}`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

  </div>
  <div class="card">

```js
Plot.plot({
  title: "Watched more than once",
  subtitle: "share of what I did play",
  width,
  height: 150,
  marginLeft: 120,
  x: { label: "Replayed →", percent: true, domain: [0, 100], grid: true },
  y: { label: null, domain: groups },
  color: colour,
  marks: [
    Plot.barX(summary, { x: "rewatchShare", y: "group", fill: "group" }),
    Plot.text(summary, { x: "rewatchShare", y: "group", text: (d) => ` ${(100 * d.rewatchShare).toFixed(0)}%`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

  </div>
</div>

## Searching

```js
const realSearches = searchData.filter((d) => !/^BV[0-9A-Za-z]{10}$/.test(d.query));
const searchGroups = groups.map((g) => ({
  group: g,
  n: realSearches.filter((d) => (d.fandoms.length ? d.fandoms[0] : "Everything else") === g).length,
}));
```

```js
Plot.plot({
  title: "What I typed into the search box",
  subtitle: `${realSearches.length.toLocaleString()} real searches; pasted video ids excluded`,
  width,
  height: 150,
  marginLeft: 120,
  x: { label: "Searches →", grid: true },
  y: { label: null, domain: groups },
  color: colour,
  marks: [
    Plot.barX(searchGroups, { x: "n", y: "group", fill: "group" }),
    Plot.text(searchGroups, { x: "n", y: "group", text: (d) => ` ${(100 * d.n / realSearches.length).toFixed(0)}%`, textAnchor: "start", fill: "currentColor" }),
    Plot.ruleX([0]),
  ],
})
```

## The rows behind all this

```js
const pick = view(Inputs.select(names, { label: "Group" }));
```

```js
Inputs.table(
  videos
    .filter((d) => d.fandoms.includes(pick))
    .map((d) => ({
      title: d.title,
      uploader: d.uploader,
      minutes: d.duration_s == null ? null : Math.round(d.duration_s / 60),
      watched: d.watched ? new Date(d.watched.last) : null,
      plays: d.watched?.repeats ?? null,
      progress: d.watched?.progress ?? null,
    })),
  {
    format: {
      progress: (p) => (p == null ? "" : `${(p * 100).toFixed(0)}%`),
      minutes: (m) => (m == null ? "live" : `${m}m`),
      watched: (d) => (d ? d.toISOString().slice(0, 10) : "never"),
    },
    width: { title: 420 },
    rows: 20,
    sort: "watched",
    reverse: true,
  }
)
```
