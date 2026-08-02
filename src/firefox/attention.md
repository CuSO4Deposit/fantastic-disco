---
theme: dashboard
title: Firefox · Attention
---

# Firefox · Attention

What pages actually held, from `moz_places_metadata` — the one table that records
reading rather than arriving. [Overview](./) is the history it sits alongside.

```js
const rhythm = FileAttachment("./data/rhythm.json").json();
const sitesData = FileAttachment("./data/sites.json").json();
const days = FileAttachment("./data/days.json").json();
```

```js
const eng = rhythm.engagement;
const sites = sitesData.sites;
const viewed = sites.filter((d) => d.view_minutes != null && d.view_minutes > 0);
const machines = days.machines;

// Only days inside some machine's engagement window. A day before it has no rows at
// all, which is not zero minutes of reading, and plotting it as zero would draw months
// of floor that never happened.
const viewDays = days.days
  .filter((d) => d.view_minutes != null)
  .map((d) => ({ ...d, date: new Date(`${d.date}T00:00:00Z`) }));
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Foreground time</h2>
    <span class="big">${Math.round(eng.view_hours).toLocaleString()}h</span>
  </div>
  <div class="card">
    <h2>Page views recorded</h2>
    <span class="big">${eng.rows.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Median page view</h2>
    <span class="big">${medianViewSeconds.toFixed(0)}s</span>
  </div>
  <div class="card">
    <h2>Sites with any</h2>
    <span class="big">${viewed.length.toLocaleString()}</span>
  </div>
</div>

```js
// From the binned histogram rather than the raw rows, which the loader does not emit:
// the bin containing the middle observation, which for log-spaced bins is close enough
// to a median and honest about being a bin.
const medianViewSeconds = (() => {
  const total = d3.sum(rhythm.view_time, (d) => d.count);
  let seen = 0;
  for (const bin of rhythm.view_time) {
    seen += bin.count;
    if (seen >= total / 2) return bin.seconds;
  }
  return 0;
})();
```

<div class="warning">

This is not time spent, and the gap is not small. Firefox accumulates
`total_view_time` only while the window is focused and the user is not idle, on a
60-second threshold, and its own source comments admit losing around two seconds at
every idle transition. A tab left open for an hour in the background contributes
nothing. Read the ${Math.round(eng.view_hours).toLocaleString()} hours above as a
floor on attention, not as how long the browser was open.

</div>

## How long a page holds

```js
Plot.plot({
  title: "Distribution of page views",
  subtitle: `${eng.rows.toLocaleString()} recorded page views. Log-spaced bins: the median is under a minute and the longest over two hours, so linear bins would put almost everything in the first bar.`,
  width,
  height: 280,
  x: {
    label: "Seconds of foreground time →",
    type: "log",
    domain: [rhythm.view_bins[0], d3.max(rhythm.view_time, (d) => d.seconds) * 1.5],
    ticks: [1, 10, 60, 600, 3600],
    tickFormat: (d) => (d < 60 ? `${d}s` : d < 3600 ? `${d / 60}m` : `${d / 3600}h`),
  },
  y: { label: "Page views", grid: true },
  marks: [
    // Bar edges come from the loader's bin list, so each bar spans its own bin rather
    // than a width Plot guesses from the point spacing.
    Plot.rectY(rhythm.view_time, {
      x1: "seconds",
      x2: (d, i) => rhythm.view_bins[rhythm.view_bins.indexOf(d.seconds) + 1] ?? d.seconds * Math.SQRT2,
      y: "count",
      fill: "var(--theme-foreground-focus)",
    }),
    Plot.ruleX([medianViewSeconds], { stroke: "var(--theme-foreground)", strokeDasharray: "3,3" }),
    Plot.ruleY([0]),
  ],
})
```

```js
display(
  htl.html`<p>The shape is one peak in the first few seconds and a long tail, not two
    modes: most page views are a glance. <b>${eng.zero_view_time.toLocaleString()}</b>
    rows accumulated no foreground time at all and are left out of the chart, which has
    no bin for zero on a log axis — those are pages that loaded and never held the
    window long enough to count. At the other end,
    <b>${eng.over_wall_clock_span.toLocaleString()}</b> rows record more view time than
    the wall-clock span between their own created and updated timestamps, so the bound
    one would expect does not quite hold; upstream does not document why.</p>`
);
```

## Reading time over the record

```js
Plot.plot({
  title: "Foreground minutes per day",
  subtitle: `${viewDays.length.toLocaleString()} machine-days inside an engagement window. Days before it are absent rather than zero.`,
  width,
  height: 280,
  x: { label: null, type: "utc" },
  y: { label: "Minutes", grid: true, zero: true },
  color: { legend: true },
  marks: [
    Plot.dot(viewDays, { x: "date", y: "view_minutes", r: 1.3, fill: "machine", fillOpacity: 0.45 }),
    Plot.lineY(viewDays, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "view_minutes", stroke: "machine", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "When the reading happens",
  subtitle: "foreground minutes per occurrence of each slot, over the engagement window's own days rather than the longer history one",
  width,
  height: 300,
  marginLeft: 50,
  x: { label: "Hour of day →", domain: d3.range(24), tickFormat: (d) => `${d}` },
  y: { label: null, domain: d3.range(7), tickFormat: (d) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] },
  color: { scheme: "YlOrRd", legend: true, label: "Minutes / day" },
  marks: [
    Plot.cell(rhythm.slots, {
      x: "hour",
      y: "weekday",
      fill: "view_minutes_per_day",
      inset: 0.5,
      tip: true,
      channels: { minutes: "view_minutes", days: "engagement_days" },
    }),
  ],
})
```

## Where the time went

```js
const topByTime = viewed.slice().sort((a, b) => b.view_minutes - a.view_minutes).slice(0, 25);
```

```js
Plot.plot({
  title: "Sites by foreground time",
  subtitle: `top 25 of ${viewed.length.toLocaleString()} sites with any recorded view time`,
  width,
  height: 620,
  marginLeft: 190,
  x: { label: "Hours", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(topByTime, {
      x: (d) => d.view_minutes / 60,
      y: "site",
      fill: "var(--theme-foreground-focus)",
      sort: { y: "x", reverse: true },
      tip: true,
      channels: { visits: "visits", days: "days", engagements: "engagements" },
    }),
    Plot.ruleX([0]),
  ],
})
```

```js
Plot.plot({
  title: "Visits against time spent",
  subtitle: "distance below the diagonal band is a site visited often and read briefly; above it, one visited rarely and read at length",
  width,
  height: 380,
  x: { label: "Visits →", type: "log", grid: true },
  y: { label: "Foreground minutes", type: "log", grid: true },
  marks: [
    Plot.dot(viewed, {
      x: "visits",
      y: "view_minutes",
      r: 2,
      fill: "var(--theme-foreground-focus)",
      fillOpacity: 0.45,
      tip: true,
      channels: { site: "site", days: "days" },
    }),
    Plot.text(topByTime.slice(0, 8), {
      x: "visits",
      y: "view_minutes",
      text: "site",
      dy: -9,
      fontSize: 10,
      fill: "var(--theme-foreground-muted)",
    }),
  ],
})
```

```js
const perVisit = viewed
  .filter((d) => d.visits >= 30)
  .map((d) => ({ ...d, seconds_per_visit: (d.view_minutes * 60) / d.visits }))
  .sort((a, b) => b.seconds_per_visit - a.seconds_per_visit);
```

```js
Plot.plot({
  title: "Seconds of attention per visit",
  subtitle: "sites with at least 30 visits, so a single long read cannot top the list. Highest and lowest fifteen.",
  width,
  height: 620,
  marginLeft: 190,
  x: { label: "Seconds per visit", grid: true },
  y: { label: null },
  marks: [
    Plot.barX([...perVisit.slice(0, 15), ...perVisit.slice(-15)], {
      x: "seconds_per_visit",
      y: "site",
      fill: "var(--theme-foreground-focus)",
      sort: { y: "x", reverse: true },
      tip: true,
      channels: { visits: "visits", minutes: "view_minutes" },
    }),
    Plot.ruleX([0]),
  ],
})
```

<div class="note">

A low figure here is not always a page skimmed. A site that redirects, or one whose
every visit is an API call the browser follows on the way to somewhere else, collects
visits that were never meant to be read. The `RELOAD`-heavy sites on the
[Overview](./) are the same effect from the other direction.

</div>

## Typing and scrolling

<div class="grid grid-cols-3">
  <div class="card">
    <h2>Key presses</h2>
    <span class="big">${eng.key_presses.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Typing time</h2>
    <span class="big">${Math.round(eng.typing_minutes / 60).toLocaleString()}h</span>
  </div>
  <div class="card">
    <h2>Scrolled</h2>
    <span class="big">${(eng.scroll_px / 1e6).toFixed(1)}M px</span>
  </div>
</div>

```js
display(
  htl.html`<p>Typing is rare and concentrated:
    <b>${eng.rows_with_keys.toLocaleString()}</b> of ${eng.rows.toLocaleString()} page
    views recorded a single key press,
    <b>${((100 * eng.rows_with_keys) / eng.rows).toFixed(0)}%</b>. Scrolling is the
    common case at <b>${((100 * eng.rows_with_scroll) / eng.rows).toFixed(0)}%</b>. The
    scroll figure is in CSS pixels, which is Firefox's unit here and not convertible to
    anything physical without a display DPI this file does not hold.</p>`
);
```

```js
display(
  htl.html`<p>Every one of the ${eng.rows.toLocaleString()} rows is typed
    <code>GENERIC</code>. Firefox has a <code>MEDIA</code> document type for
    video-serving pages and writes it nowhere in this archive, so anything built on that
    distinction would be building on an unexercised code path.</p>`
);
```

## Pages, not sites

```js
const pages = sitesData.pages;
```

```js
const pageMachine = view(
  Inputs.select([...new Set(pages.map((d) => d.machine))], { label: "Machine" })
);
```

```js
const shown = pages.filter((d) => d.machine === pageMachine).slice(0, 20);
```

```js
// A bar's `y` is its identity, so two pages sharing a label land in one band and draw
// over each other — the chart would show one page's time and silently drop the other's.
// Titles do repeat, and so do truncated paths: a single-page app writes one title for
// every URL under it, and five of them here differ only past the 22nd character of a
// base64 path. So the label is disambiguated by path and then forced unique.
const labelled = (() => {
  const byTitle = d3.rollup(shown, (v) => v.length, (d) => d.title ?? d.url);
  const used = new Map();
  return shown.map((d) => {
    const title = d.title ?? d.url;
    let label;
    if (byTitle.get(title) === 1) {
      label = truncate(title);
    } else {
      let tail = d.url;
      try {
        const parsed = new URL(d.url);
        tail = parsed.pathname + parsed.search;
      } catch {
        // A URL Firefox stored that the browser will not parse; the raw string still
        // disambiguates, which is all this needs.
      }
      // Kept from the end: these paths share a long prefix and differ at the tail.
      label = `${truncate(title, 30)} · …${tail.slice(-20)}`;
    }
    // Last resort, so no two bars can ever collapse into one band regardless of how
    // the URLs are shaped.
    const seen = (used.get(label) ?? 0) + 1;
    used.set(label, seen);
    return { ...d, label: seen === 1 ? label : `${label} (${seen})` };
  });
})();
```

```js
Plot.plot({
  title: `Most-read pages on ${pageMachine}`,
  subtitle: "a single URL, not a site. Per machine because a page's identity here is (machine, URL) — the same URL on two profiles is two records.",
  width,
  height: 520,
  marginLeft: 300,
  x: { label: "Minutes", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(labelled, {
      x: "view_minutes",
      y: "label",
      fill: "var(--theme-foreground-focus)",
      sort: { y: "x", reverse: true },
      tip: true,
      channels: { site: "site", views: "engagements", url: "url" },
    }),
    Plot.ruleX([0]),
  ],
})
```

```js
function truncate(text, n = 46) {
  return text.length > n ? `${text.slice(0, n - 1)}…` : text;
}
```

<div class="note">

One page view is one row, and Firefox starts a fresh row after an hour without
updates — so a tab kept open across a day contributes several. A page with many rows
was not necessarily navigated to that many times.

</div>
