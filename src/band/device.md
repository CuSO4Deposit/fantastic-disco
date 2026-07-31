---
theme: dashboard
title: Device
---

# Device

The band itself rather than the wearer: how the battery is holding up over two years.
Back to [Band](./).

```js
const device = FileAttachment("./data/device.json").json();
```

```js
const levels = device.levels.map((d) => ({ ...d, when: new Date(d.when) }));
const runs = device.discharge_runs.map((d) => ({ ...d, start: new Date(d.start) }));
// Runs that lost too few points to read a rate from are mostly the band's own
// rounding, so they are kept out of every figure below.
// Runs too short to read a rate from are kept out of every figure below: a small drop
// is mostly rounding, and a short window measures whatever the band happened to be
// doing rather than a baseline.
const usable = runs.filter(
  (d) => d.drop >= device.min_informative_drop && d.hours >= device.min_informative_hours
);
const rate = d3.median(usable, (d) => d.percent_per_day);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Device</h2>
    <span class="big">${device.device.name}</span>
  </div>
  <div class="card">
    <h2>Charge cycles</h2>
    <span class="big">${runs.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Drain</h2>
    <span class="big">${rate.toFixed(1)}%/day</span>
  </div>
  <div class="card">
    <h2>Firmware</h2>
    <span class="big">${device.device.model}</span>
  </div>
</div>

## Battery level

```js
Plot.plot({
  title: "Every battery reading",
  subtitle: `${levels.length.toLocaleString()} readings. Each sawtooth is one charge cycle.`,
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Charge", domain: [0, 100], grid: true, tickFormat: (d) => `${d}%` },
  marks: [
    Plot.lineY(levels, { x: "when", y: "level", stroke: "var(--theme-foreground-focus)", strokeWidth: 1 }),
    Plot.ruleY([0]),
  ],
})
```

## Is it aging

```js
Plot.plot({
  title: "Drain rate per discharge run",
  subtitle: `${usable.length.toLocaleString()} of ${runs.length.toLocaleString()} runs, those lasting at least ${device.min_informative_hours}h and losing at least ${device.min_informative_drop} points`,
  width,
  height: 260,
  x: { label: null, type: "utc" },
  y: { label: "Charge lost per day", grid: true, zero: true, tickFormat: (d) => `${d}%` },
  marks: [
    Plot.dot(usable, { x: "start", y: "percent_per_day", r: 2.5, fill: "var(--theme-foreground-faint)", tip: true, channels: { hours: "hours", drop: "drop" } }),
    Plot.linearRegressionY(usable, { x: "start", y: "percent_per_day", stroke: "var(--theme-foreground-focus)", fillOpacity: 0.1 }),
    Plot.ruleY([0]),
  ],
})
```

```js
// Correlation on the same runs the chart draws, so the number and the line cannot
// disagree.
const xs = usable.map((d) => +d.start);
const ys = usable.map((d) => d.percent_per_day);
const mx = d3.mean(xs);
const my = d3.mean(ys);
const sxy = d3.sum(xs.map((x, i) => (x - mx) * (ys[i] - my)));
const sxx = d3.sum(xs.map((x) => (x - mx) ** 2));
const syy = d3.sum(ys.map((y) => (y - my) ** 2));
const r = sxy / Math.sqrt(sxx * syy);
const firstThird = usable.slice(0, Math.floor(usable.length / 3));
const lastThird = usable.slice(-Math.floor(usable.length / 3));
```

```js
display(
  htl.html`<p>The battery is draining faster than it used to:
    <b>${d3.median(firstThird, (d) => d.percent_per_day).toFixed(1)}%</b> per day
    over the earliest third of these runs against
    <b>${d3.median(lastThird, (d) => d.percent_per_day).toFixed(1)}%</b> over the
    most recent third, correlation ${r.toFixed(2)} against time. At the current rate
    a full charge lasts about ${(100 / rate).toFixed(0)} days, down from roughly
    ${(100 / d3.median(firstThird, (d) => d.percent_per_day)).toFixed(0)}.</p>`
);
```

<div class="note">

Read the *rate*, not a projected runtime. An earlier version of this page divided each
run's duration by its drop to get "days a full charge would last", which for runs of
one or two points produced values over 400 days — enough to dominate the median and
invent a trend in the opposite direction.

Short runs are excluded because the rate depends on the window: runs under a day come
out near 14%/day against 3%/day for runs over four, since a short window catches
whatever the band was doing rather than a baseline. The most recent run is always
partial for the same reason. The trend is the same with or without those runs
(correlation 0.49 either way), so this narrows the claim rather than supporting it.

Two caveats even so. Drain depends on how the band was used, not only on the cell:
continuous heart rate monitoring and screen wakes both cost charge, and neither is
constant over two years. And a percent is whatever the firmware says it is, which is
itself a model of a battery that may drift as the cell ages.

</div>
