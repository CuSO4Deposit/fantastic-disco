---
theme: dashboard
title: Band
---

# Band

Steps, sleep, heart rate and stress from a Mi Smart Band 5, by way of Gadgetbridge.
[Sleep](./sleep) goes into the nights in detail; [Device](./device) is the band
itself rather than the body wearing it.

```js
const days = FileAttachment("./data/days.json").json();
const rhythm = FileAttachment("./data/rhythm.json").json();
```

```js
// Weekday from the date string via a fixed UTC instant, not from a browser-local
// Date: `new Date("2026-07-30T00:00")` is midnight *where the browser is*, so
// getUTCDay() on it can name the previous day. 0 is Monday, to match the axis labels.
function weekdayIndex(isoDate) {
  return (new Date(`${isoDate}T00:00:00Z`).getUTCDay() + 6) % 7;
}

// Dates are anchored at UTC midnight to match `x: {type: "utc"}` on every chart
// below. Parsing "2026-07-30T00:00" instead gives midnight where the *browser* is,
// which a utc axis then renders as the 29th for anyone east of UTC.
const dayRows = days.days.map((d) => ({
  ...d,
  date: new Date(`${d.date}T00:00:00Z`),
  weekday: weekdayIndex(d.date),
}));
const nights = days.nights.map((d) => ({
  ...d,
  date: new Date(`${d.date}T00:00:00Z`),
  asleep_minutes: d.light_minutes + d.deep_minutes,
}));

// Days the band actually spent on a wrist for most of the day. A day it sat in a
// drawer is not a day of few steps, and averaging it in drags every rate down.
const WORN_THRESHOLD = 720;
const wornDays = dayRows.filter((d) => d.worn_minutes >= WORN_THRESHOLD);
const missingDays = d3.sum(days.gaps, (g) => g.days);
const goal = days.steps_goal;
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Days recorded</h2>
    <span class="big">${dayRows.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Median steps</h2>
    <span class="big">${d3.median(wornDays, (d) => d.steps).toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Median sleep</h2>
    <span class="big">${(d3.median(nights, (d) => d.asleep_minutes) / 60).toFixed(1)}h</span>
  </div>
  <div class="card">
    <h2>Resting heart rate</h2>
    <span class="big">${d3.median(nights.filter((d) => d.heart_rate_low != null), (d) => d.heart_rate_low).toFixed(0)}</span>
  </div>
</div>

```js
// A JS block rather than an inline ${...}: an inline expression spanning blank lines
// ends the Markdown paragraph, and the rest renders as literal source.
if (missingDays > 0) {
  const longest = d3.greatest(days.gaps, (g) => g.days);
  display(
    htl.html`<div class="warning">
      ${missingDays.toLocaleString()} days are missing entirely, the longest run
      ${longest.days} days after ${longest.after}. The band buffers about a week and
      then overwrites, so a stretch that was never synced is gone rather than empty —
      no later backup can recover it. Every count here is over the
      ${dayRows.length.toLocaleString()} days that were recorded.
    </div>`
  );
}
```

## Steps

```js
Plot.plot({
  title: "Steps per day",
  subtitle: `${wornDays.length.toLocaleString()} days with the band worn at least ${WORN_THRESHOLD / 60}h. Gaps in the line are gaps in the record.`,
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Steps", grid: true, zero: true },
  marks: [
    goal ? Plot.ruleY([goal], { stroke: "var(--theme-foreground-muted)", strokeDasharray: "3,3" }) : null,
    goal ? Plot.text([goal], { x: d3.min(wornDays, (d) => d.date), y: goal, text: [`goal ${goal.toLocaleString()}`], dy: -8, textAnchor: "start", fill: "var(--theme-foreground-muted)" }) : null,
    Plot.dot(wornDays, { x: "date", y: "steps", r: 1.2, fill: "var(--theme-foreground-faint)" }),
    // A 14-day window: enough to pull the trend out of day-to-day noise without
    // flattening a change that lasts a few weeks.
    Plot.lineY(wornDays, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "steps", stroke: "var(--theme-foreground-focus)", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

```js
const metGoal = goal ? wornDays.filter((d) => d.steps >= goal).length : 0;
```

```js
if (goal) {
  display(
    htl.html`<p>The goal of ${goal.toLocaleString()} steps was met on
      <b>${metGoal.toLocaleString()}</b> of ${wornDays.length.toLocaleString()} worn
      days, <b>${((100 * metGoal) / wornDays.length).toFixed(0)}%</b>. Median day is
      ${d3.median(wornDays, (d) => d.steps).toLocaleString()} steps.</p>`
  );
}
```

```js
Plot.plot({
  title: "When the walking happens",
  subtitle: "steps per minute recorded in each hour, so gaps don't skew it",
  width,
  height: 260,
  x: { label: "Hour of day →", domain: d3.range(24), tickFormat: (d) => `${d}` },
  y: { label: "Steps / minute", grid: true },
  marks: [
    Plot.barY(rhythm.slots, Plot.groupX({ y: "median" }, { x: "hour", y: "steps_per_minute", fill: "var(--theme-foreground-focus)" })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Weekday and weekend",
  subtitle: "median steps per worn day; 0 is Monday",
  width,
  height: 260,
  marginLeft: 50,
  x: { label: "Steps", grid: true },
  y: { label: null, tickFormat: (d) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] },
  marks: [
    Plot.barX(wornDays, Plot.groupY({ x: "median" }, { y: "weekday", x: "steps", fill: "var(--theme-foreground-focus)" })),
    Plot.ruleX([0]),
  ],
})
```

## Heart rate

```js
const hrTotal = d3.sum(rhythm.heart_rate, (d) => d.minutes);
const hrBin = rhythm.hr_bin;

// Long form, one row per (bin, state). `fill` names a column, so passing the string
// "asleep" for a column that does not exist yields undefined for every row and draws
// nothing at all — the chart renders, empty, with axes intact.
const hrByState = rhythm.heart_rate.flatMap((d) => [
  { bpm: d.bpm, state: "asleep", minutes: d.asleep_minutes },
  { bpm: d.bpm, state: "awake", minutes: d.minutes - d.asleep_minutes },
]);
```

```js
Plot.plot({
  title: "Heart rate, every measured minute",
  subtitle: `${hrTotal.toLocaleString()} minutes with a valid reading, in ${hrBin} bpm bins. Failed readings are excluded, not counted as zero.`,
  width,
  height: 260,
  x: { label: "bpm →", domain: [d3.min(rhythm.heart_rate, (d) => d.bpm), d3.max(rhythm.heart_rate, (d) => d.bpm) + hrBin] },
  y: { label: "Minutes", grid: true },
  color: { legend: true, domain: ["asleep", "awake"], range: ["var(--theme-foreground-focus)", "var(--theme-foreground-faint)"] },
  marks: [
    Plot.rectY(hrByState, { x1: "bpm", x2: (d) => d.bpm + hrBin, y: "minutes", fill: "state", tip: true }),
    Plot.ruleY([0]),
  ],
})
```

The two populations barely overlap, which is what makes a resting rate recoverable at
all: this band records no resting heart rate series of its own, so the figure in the
card above is the 5th percentile of each night's sleeping minutes.

```js
Plot.plot({
  title: "Resting heart rate over time",
  subtitle: "5th percentile of each night's sleeping minutes",
  width,
  height: 240,
  x: { label: null, type: "utc" },
  y: { label: "bpm", grid: true },
  marks: [
    Plot.dot(nights.filter((d) => d.heart_rate_low != null), { x: "date", y: "heart_rate_low", r: 1.2, fill: "var(--theme-foreground-faint)" }),
    Plot.lineY(nights.filter((d) => d.heart_rate_low != null), Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "heart_rate_low", stroke: "var(--theme-foreground-focus)", strokeWidth: 2 })),
  ],
})
```

```js
Plot.plot({
  title: "Heart rate through the day",
  subtitle: "median of each hour",
  width,
  height: 240,
  x: { label: "Hour of day →", domain: d3.range(24) },
  y: { label: "bpm", grid: true },
  marks: [
    Plot.lineY(rhythm.slots.filter((d) => d.heart_rate_median != null), Plot.groupX({ y: "median" }, { x: "hour", y: "heart_rate_median", stroke: "var(--theme-foreground-focus)", strokeWidth: 2, curve: "catmull-rom" })),
    Plot.dot(rhythm.slots.filter((d) => d.heart_rate_median != null), Plot.groupX({ y: "median" }, { x: "hour", y: "heart_rate_median", fill: "var(--theme-foreground-focus)", r: 2 })),
  ],
})
```

## Stress

```js
const stressTotal = rhythm.stress_readings;
const stressBin = rhythm.stress_bin;
```

```js
Plot.plot({
  title: "Stress readings",
  subtitle: `${stressTotal.toLocaleString()} readings, roughly one per 5 minutes when measured`,
  width,
  height: 240,
  x: { label: "Stress →", domain: [0, 100] },
  y: { label: "Readings", grid: true },
  marks: [
    Plot.rectY(rhythm.stress, { x1: "value", x2: (d) => d.value + stressBin, y: "count", fill: "var(--theme-foreground-focus)", tip: true }),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Stress against heart rate",
  subtitle: `${d3.sum(rhythm.stress_vs_heart_rate, (d) => d.count).toLocaleString()} readings paired with a reading from the same minute`,
  width,
  height: 300,
  x: { label: "Stress →", domain: [0, 100] },
  y: { label: "bpm", domain: [d3.min(rhythm.stress_vs_heart_rate, (d) => d.bpm), d3.max(rhythm.stress_vs_heart_rate, (d) => d.bpm) + hrBin] },
  color: { scheme: "YlGnBu", label: "Minutes", legend: true, type: "sqrt" },
  marks: [
    Plot.rect(rhythm.stress_vs_heart_rate, { x1: "stress", x2: (d) => d.stress + stressBin, y1: "bpm", y2: (d) => d.bpm + hrBin, fill: "count", tip: true }),
  ],
})
```

```js
// Weighted least squares over the binned counts. Bin midpoints, since a bin's label
// is its lower edge.
const pairs = rhythm.stress_vs_heart_rate;
const wSum = d3.sum(pairs, (d) => d.count);
const mx = d3.sum(pairs, (d) => (d.stress + stressBin / 2) * d.count) / wSum;
const my = d3.sum(pairs, (d) => (d.bpm + hrBin / 2) * d.count) / wSum;
const sxy = d3.sum(pairs, (d) => d.count * (d.stress + stressBin / 2 - mx) * (d.bpm + hrBin / 2 - my));
const sxx = d3.sum(pairs, (d) => d.count * (d.stress + stressBin / 2 - mx) ** 2);
const syy = d3.sum(pairs, (d) => d.count * (d.bpm + hrBin / 2 - my) ** 2);
const r = sxy / Math.sqrt(sxx * syy);
```

```js
display(
  htl.html`<p>The two move together, correlation <b>${r.toFixed(2)}</b> across
    ${wSum.toLocaleString()} paired minutes. That is worth reading as a statement
    about the band rather than about the wearer: whatever the firmware computes as
    stress, it is derived largely from heart rate, so this is closer to a check that
    the two series are consistent than an independent finding.
    ${rhythm.stress_without_heart_rate.toLocaleString()} readings had no valid heart
    rate in the same minute and are left out.</p>`
);
```

## What the band was doing

```js
const kinds = Object.entries(rhythm.kind_minutes)
  .map(([kind, minutes]) => ({ kind, minutes }))
  .sort((a, b) => b.minutes - a.minutes);
const kindTotal = d3.sum(kinds, (d) => d.minutes);
```

```js
Plot.plot({
  title: "Every recorded minute, by what the band called it",
  subtitle: `${kindTotal.toLocaleString()} minutes. NONWEAR and CHARGING are minutes the band was off a wrist.`,
  width,
  height: 200,
  marginLeft: 110,
  x: { label: "Minutes", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(kinds, { x: "minutes", y: "kind", fill: "var(--theme-foreground-focus)", sort: { y: "x", reverse: true }, tip: true }),
    Plot.ruleX([0]),
  ],
})
```

Worth knowing how this is derived: the band stores "same as before" for most minutes
rather than repeating a state, so 84% of rows carry no activity type at all and
inherit one. CPI resolves that, and refuses to carry a state across a gap longer than
an hour — which is why `UNSET` appears at all, and why it stays tiny.
