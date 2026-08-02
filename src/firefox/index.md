---
theme: dashboard
title: Firefox
---

# Firefox

Browsing history from archived copies of `places.sqlite`, one per machine.
[Attention](./attention) is what pages actually held; [Library](./library) is what was
kept — bookmarks and downloads.

```js
const days = FileAttachment("./data/days.json").json();
const rhythm = FileAttachment("./data/rhythm.json").json();
```

```js
// Dates are anchored at UTC midnight to match `x: {type: "utc"}` on the charts below.
// Parsing "2026-08-02" as a local date instead gives midnight where the *browser* is,
// which a utc axis then renders as the 1st for anyone east of UTC.
const dayRows = days.days.map((d) => ({
  ...d,
  date: new Date(`${d.date}T00:00:00Z`),
}));

const machines = days.machines;
const visitTotal = d3.sum(dayRows, (d) => d.visits);
const reloadTotal = d3.sum(dayRows, (d) => d.reloads);

// One row per date, summing the machines: a day is a day whichever browser recorded it.
// Kept separate from `dayRows`, which the per-machine chart needs unpooled.
const perDate = Array.from(
  d3.rollup(dayRows, (v) => d3.sum(v, (d) => d.visits), (d) => d.date.getTime()),
  ([time, visits]) => ({ date: new Date(time), visits })
).sort((a, b) => a.date - b.date);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Visits</h2>
    <span class="big">${visitTotal.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Days with history</h2>
    <span class="big">${perDate.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Machines</h2>
    <span class="big">${machines.length}</span>
  </div>
  <div class="card">
    <h2>Busiest day</h2>
    <span class="big">${d3.max(perDate, (d) => d.visits).toLocaleString()}</span>
  </div>
</div>

```js
// A JS block rather than an inline ${...}: an inline expression spanning blank lines
// ends the Markdown paragraph and the rest renders as literal source.
display(
  htl.html`<div class="warning">
    A day with no visits is not necessarily a day away from the browser. Firefox expires
    history when the database outgrows its size limit, on no schedule this file records,
    so the early end of every series is where expiration last cut rather than where the
    browsing began. The record starts at
    ${d3.min(machines, (m) => m.history_from)} only in the sense that nothing older
    survived.
  </div>`
);
```

## What each machine can answer for

```js
// Long form, one row per (machine, series). Two marks reading `x1`/`x2` off separate
// columns would need two legends; a channel is a column name, so the reshape is what
// lets one `fill` scale label both.
const windows = machines.flatMap((m) => [
  {
    machine: m.machine,
    series: "History",
    from: new Date(`${m.history_from}T00:00:00Z`),
    to: new Date(`${m.history_to}T00:00:00Z`),
    days: m.days_with_history,
  },
  ...(m.engagement_from
    ? [
        {
          machine: m.machine,
          series: "Engagement",
          from: new Date(`${m.engagement_from}T00:00:00Z`),
          to: new Date(`${m.engagement_to}T00:00:00Z`),
          days: m.days_with_engagement,
        },
      ]
    : []),
]);
```

```js
Plot.plot({
  title: "How far back each snapshot reaches",
  subtitle:
    "engagement rows are expired on age, long before the visits they describe — so view time simply does not exist at the left of either bar",
  width,
  height: 40 + windows.length * 34,
  marginLeft: 150,
  x: { label: null, type: "utc", grid: true },
  y: { label: null, tickFormat: (d) => d },
  color: { legend: true, domain: ["History", "Engagement"], scheme: "Set2" },
  marks: [
    Plot.barX(windows, {
      x1: "from",
      x2: "to",
      y: "machine",
      fy: "series",
      fill: "series",
      tip: true,
      channels: { days: "days" },
    }),
  ],
})
```

```js
display(
  htl.html`<p>${machines
    .map(
      (m) =>
        htl.html`<b>${m.machine}</b> holds ${m.days_with_history.toLocaleString()} days
          of history from ${m.history_from}, and engagement for
          ${m.days_with_engagement.toLocaleString()} of them from
          ${m.engagement_from ?? "never"}. `
    )}
    Neither figure is a retention policy: the two windows differ from each other, so no
    single constant explains them.</p>`
);
```

## Visits over time

```js
Plot.plot({
  title: "Visits per day",
  subtitle: `${visitTotal.toLocaleString()} visits across ${perDate.length.toLocaleString()} days, both machines pooled. The line is a 14-day median.`,
  width,
  height: 280,
  x: { label: null, type: "utc" },
  y: { label: "Visits", grid: true, zero: true },
  marks: [
    Plot.dot(perDate, { x: "date", y: "visits", r: 1.2, fill: "var(--theme-foreground-faint)" }),
    Plot.lineY(perDate, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "visits", stroke: "var(--theme-foreground-focus)", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Per machine",
  subtitle: "14-day median, so the handover between machines is visible rather than averaged away",
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Visits", grid: true, zero: true },
  color: { legend: true },
  marks: [
    Plot.lineY(dayRows, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "visits", stroke: "machine", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Distinct sites per day",
  subtitle: "how wide a day's browsing was, against how many pages it loaded",
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Sites", grid: true, zero: true },
  color: { legend: true },
  marks: [
    Plot.dot(dayRows, { x: "date", y: "sites", r: 1.2, fill: "machine", fillOpacity: 0.4 }),
    Plot.lineY(dayRows, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "sites", stroke: "machine", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

## How pages were reached

```js
const types = Object.entries(days.visit_types).map(([type, count]) => ({ type, count }));
const sources = Object.entries(days.visit_sources).map(([source, count]) => ({ source, count }));
```

```js
Plot.plot({
  title: "Transition type",
  subtitle: `${visitTotal.toLocaleString()} visits. RELOAD and DOWNLOAD are the two Firefox leaves out of its own visit counter.`,
  width,
  height: 220,
  marginLeft: 150,
  x: { label: "Visits", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(types, { x: "count", y: "type", fill: "var(--theme-foreground-focus)", sort: { y: "x", reverse: true }, tip: true }),
    Plot.ruleX([0]),
  ],
})
```

```js
const counted = d3.sum(dayRows, (d) => d.counted_visits);
```

```js
display(
  htl.html`<p>Firefox's own <code>visit_count</code> would report
    <b>${counted.toLocaleString()}</b> of these
    ${visitTotal.toLocaleString()} visits: it excludes reloads and downloads, which here
    is ${(visitTotal - counted).toLocaleString()} rows, <b>${((100 * (visitTotal - counted)) / visitTotal).toFixed(1)}%</b>.
    The ${reloadTotal.toLocaleString()} reloads are the bulk of that. A page reloaded
    twenty times and never navigated to reports zero visits in the browser's UI while
    holding twenty rows in the file.</p>`
);
```

```js
Plot.plot({
  title: "Where the navigation came from",
  subtitle: "Firefox's own source flag. ORGANIC is the default and dominates; SPONSORED appearing once at all is the notable part.",
  width,
  height: 200,
  marginLeft: 150,
  x: { label: "Visits", grid: true, type: "symlog" },
  y: { label: null },
  marks: [
    Plot.barX(sources, { x: "count", y: "source", fill: "var(--theme-foreground-focus)", sort: { y: "x", reverse: true }, tip: true }),
    Plot.ruleX([0]),
  ],
})
```

```js
display(
  htl.html`<p><b>${days.visits_without_referrer.toLocaleString()}</b> visits carry no
    referrer, <b>${((100 * days.visits_without_referrer) / visitTotal).toFixed(0)}%</b>.
    That is not the same as ${days.visits_without_referrer.toLocaleString()} URLs typed
    from scratch: the field is empty when there genuinely was no referrer, when the
    referring visit has since been expired, and when the referring page is one this
    snapshot no longer holds — three cases the file does not distinguish. The
    ${(days.visit_types.TYPED ?? 0).toLocaleString()} TYPED transitions above are the
    number that actually means "typed or chosen from the address bar".</p>`
);
```

## Rhythm

```js
const slots = rhythm.slots;
const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
```

```js
Plot.plot({
  title: "Hour of the week",
  subtitle: "visits per occurrence of each slot, so a weekday the archive covers more of doesn't look busier for it",
  width,
  height: 300,
  marginLeft: 50,
  x: { label: "Hour of day →", domain: d3.range(24), tickFormat: (d) => `${d}` },
  y: { label: null, domain: d3.range(7), tickFormat: (d) => weekdays[d] },
  color: { scheme: "YlGnBu", legend: true, label: "Visits / day" },
  marks: [
    Plot.cell(slots, {
      x: "hour",
      y: "weekday",
      fill: "visits_per_day",
      inset: 0.5,
      tip: true,
      channels: { visits: "visits", days: "days" },
    }),
  ],
})
```

```js
Plot.plot({
  title: "By hour, pooled over the week",
  subtitle: "typed visits shown against the total, since the address bar is used at different hours than links are followed",
  width,
  height: 260,
  x: { label: "Hour of day →", domain: d3.range(24), tickFormat: (d) => `${d}` },
  y: { label: "Visits", grid: true },
  marks: [
    Plot.barY(slots, Plot.groupX({ y: "sum" }, { x: "hour", y: "visits", fill: "var(--theme-foreground-faint)" })),
    Plot.barY(slots, Plot.groupX({ y: "sum" }, { x: "hour", y: "typed", fill: "var(--theme-foreground-focus)" })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Weekday and weekend",
  subtitle: "visits per occurrence of each weekday; 0 is Monday",
  width,
  height: 240,
  marginLeft: 50,
  x: { label: "Visits per day", grid: true },
  y: { label: null, tickFormat: (d) => weekdays[d] },
  marks: [
    Plot.barX(slots, Plot.groupY({ x: "sum" }, { y: "weekday", x: "visits_per_day", fill: "var(--theme-foreground-focus)" })),
    Plot.ruleX([0]),
  ],
})
```

## Schemes

```js
const schemes = Object.entries(days.schemes).map(([scheme, count]) => ({ scheme, count }));
```

```js
display(
  htl.html`<p>${schemes
    .map((s, i) => htl.html`${i ? ", " : ""}<b>${s.count.toLocaleString()}</b> ${s.scheme}`)}.
    The <code>file:</code> visits are local files opened in the browser; they are real
    navigations and stay in every total here, filed under
    <i>(local files)</i> wherever a site name is wanted.</p>`
);
```
