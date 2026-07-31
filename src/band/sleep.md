---
theme: dashboard
title: Sleep
---

# Sleep

Every night the band recorded, from [Band](./). A night is keyed by the date it
started, so one that begins at 01:00 belongs to the evening before rather than
splitting across two dates.

```js
const days = FileAttachment("./data/days.json").json();
```

```js
// Wall-clock hour as recorded, read off the ISO string rather than through Date.
// `getHours()` converts to the *browser's* timezone: on a UTC machine an 01:58+08:00
// bedtime came out as 18:06, an evening. The loader already emits the offset it means,
// so the characters are the answer and no conversion is wanted.
function clockHour(iso) {
  return +iso.slice(11, 13) + +iso.slice(14, 16) / 60;
}

// Same reasoning for the weekday: derive it from the date string at a fixed instant
// rather than from a browser-local Date. 0 is Monday, to match the axis labels.
function weekdayIndex(isoDate) {
  return (new Date(`${isoDate}T00:00:00Z`).getUTCDay() + 6) % 7;
}

const nights = days.nights.map((d) => ({
  ...d,
  // UTC midnight, to match `x: {type: "utc"}`. Browser-local midnight would render as
  // the previous day for anyone east of UTC.
  date: new Date(`${d.date}T00:00:00Z`),
  // Kept as characters for labels: formatting the Date back to a string would run it
  // through the browser's timezone and can name the wrong day.
  date_str: d.date,
  weekday: weekdayIndex(d.date),
  start: new Date(d.start),
  end: new Date(d.end),
  asleep_minutes: d.light_minutes + d.deep_minutes,
  // Hours since local midnight, allowed past 24 so a 01:00 bedtime reads as 25
  // rather than jumping to the other end of the axis.
  bedtime: (() => {
    const h = clockHour(d.start);
    return h < 12 ? h + 24 : h;
  })(),
  deep_share: (d.deep_minutes / (d.light_minutes + d.deep_minutes)) || 0,
}));

// Waking has to share the bedtime axis, so it continues past 24 rather than wrapping
// to 0. Deriving it from bedtime plus elapsed time keeps the pair on one convention:
// reading both off the clock put a 22:00 wake and a 22:00 bedtime at the same height
// while meaning opposite things, and 57 nights woke after noon, colliding with the
// evening end of the scale.
for (const n of nights) {
  n.wake = n.bedtime + n.span_minutes / 60;
}
const asleepHours = nights.map((d) => d.asleep_minutes / 60);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Nights</h2>
    <span class="big">${nights.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Median asleep</h2>
    <span class="big">${(d3.median(asleepHours)).toFixed(1)}h</span>
  </div>
  <div class="card">
    <h2>Median bedtime</h2>
    <span class="big">${formatClock(d3.median(nights, (d) => d.bedtime))}</span>
  </div>
  <div class="card">
    <h2>Median wake</h2>
    <span class="big">${formatClock(d3.median(nights, (d) => d.wake))}</span>
  </div>
</div>

```js
// Takes hours that may run past 24 (or below 0) and wraps to a wall clock. Both the
// axis and the cards feed it values on the continuous scale.
function formatClock(hours) {
  const wrapped = ((hours % 24) + 24) % 24;
  let h = Math.floor(wrapped);
  let m = Math.round((wrapped - h) * 60);
  if (m === 60) {
    m = 0;
    h = (h + 1) % 24;
  }
  return `${h}:${String(m).padStart(2, "0")}`;
}
```

<div class="note">

Sessions under three hours are left out, so naps and misdetections don't sit beside
whole nights as if they were comparable. A night is one run of sleep, allowing
awakenings of up to an hour without splitting it in two.

</div>

## How much

```js
Plot.plot({
  title: "Hours asleep per night",
  subtitle: `${nights.length.toLocaleString()} nights. Gaps in the line are gaps in the record, not sleepless nights.`,
  width,
  height: 280,
  x: { label: null, type: "utc" },
  y: { label: "Hours asleep", grid: true, domain: [0, d3.max(asleepHours)] },
  marks: [
    Plot.dot(nights, { x: "date", y: (d) => d.asleep_minutes / 60, r: 1.4, fill: "var(--theme-foreground-faint)" }),
    Plot.lineY(nights, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: (d) => d.asleep_minutes / 60, stroke: "var(--theme-foreground-focus)", strokeWidth: 2 })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "Distribution of nights",
  subtitle: `median ${d3.median(asleepHours).toFixed(1)}h`,
  width,
  height: 240,
  x: { label: "Hours asleep →", domain: [0, d3.max(asleepHours)] },
  y: { label: "Nights", grid: true },
  marks: [
    Plot.rectY(asleepHours, Plot.binX({ y: "count" }, { x: (d) => d, thresholds: 30, fill: "var(--theme-foreground-focus)" })),
    Plot.ruleX([d3.median(asleepHours)], { stroke: "var(--theme-foreground)", strokeDasharray: "3,3" }),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "By day of week",
  subtitle: "median hours asleep, by the night's starting day",
  width,
  height: 240,
  marginLeft: 50,
  x: { label: "Hours asleep", grid: true },
  y: { label: null, tickFormat: (d) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] },
  marks: [
    Plot.barX(nights, Plot.groupY({ x: "median" }, { y: "weekday", x: (d) => d.asleep_minutes / 60, fill: "var(--theme-foreground-focus)" })),
    Plot.ruleX([0]),
  ],
})
```

## When

```js
Plot.plot({
  title: "Bedtime and waking",
  subtitle: "each vertical line is one night, from falling asleep down to waking",
  width,
  height: 300,
  x: { label: null, type: "utc" },
  y: {
    label: "Clock time →",
    // Pinned from the data on the continuous scale both series share, then reversed so
    // later-in-the-night reads downward. An explicit domain over hardcoded bounds:
    // these run past 24 by construction and the extent shifts with the data.
    domain: [d3.min(nights, (d) => d.bedtime) - 0.5, d3.max(nights, (d) => d.wake) + 0.5],
    reverse: true,
    grid: true,
    // Ticks land on the continuous scale, so 26 must print as 2:00.
    tickFormat: (d) => formatClock(d),
  },
  color: { legend: true, domain: ["asleep by", "awake at"], range: ["var(--theme-foreground-focus)", "var(--theme-blue)"] },
  marks: [
    Plot.ruleX(nights, { x: "date", y1: "bedtime", y2: "wake", stroke: "var(--theme-foreground-faint)", strokeWidth: 1 }),
    Plot.lineY(nights, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "bedtime", stroke: () => "asleep by", strokeWidth: 2 })),
    Plot.lineY(nights, Plot.windowY({ k: 14, reduce: "median" }, { x: "date", y: "wake", stroke: () => "awake at", strokeWidth: 2 })),
  ],
})
```

```js
const lateNights = nights.filter((d) => d.bedtime >= 24).length;
```

```js
display(
  htl.html`<p><b>${((100 * lateNights) / nights.length).toFixed(0)}%</b> of nights
    began after midnight. Median bedtime is
    ${formatClock(d3.median(nights, (d) => d.bedtime))} and median waking
    ${formatClock(d3.median(nights, (d) => d.wake))}.</p>`
);
```

## Staging, and why to distrust it

```js
const deepShare = d3.sum(nights, (d) => d.deep_minutes) / d3.sum(nights, (d) => d.asleep_minutes);
```

```js
Plot.plot({
  title: "Deep sleep as a share of each night",
  subtitle: `overall ${(100 * deepShare).toFixed(1)}%`,
  width,
  height: 240,
  // percent: true is a scale transform — it multiplies before the scale, so the
  // domain belongs in percent space even though the data is 0..1.
  x: { label: "Deep sleep →", percent: true, domain: [0, 100] },
  y: { label: "Nights", grid: true },
  marks: [
    Plot.rectY(nights, Plot.binX({ y: "count" }, { x: "deep_share", thresholds: 30, fill: "var(--theme-foreground-focus)" })),
    Plot.ruleY([0]),
  ],
})
```

<div class="warning">

**${(100 * deepShare).toFixed(1)}%** deep sleep is well below the 13–23% usually
quoted for adults. Read that as a fact about this band, not about the sleeper: a Mi
Band 5 through Gadgetbridge has no REM staging at all, only light and deep, and its
deep detection is visibly weak. The totals above — time asleep, bedtime, waking — are
sound; the split between light and deep is the part not to build an argument on.

</div>

## Time in bed against time asleep

```js
Plot.plot({
  title: "Awake time within a night",
  subtitle: "distance from the diagonal is time awake between falling asleep and getting up",
  width,
  height: 320,
  aspectRatio: 1,
  x: { label: "Hours from falling asleep to waking →", grid: true },
  y: { label: "Hours actually asleep", grid: true },
  marks: [
    Plot.link([0], { x1: 0, y1: 0, x2: d3.max(nights, (d) => d.span_minutes / 60), y2: d3.max(nights, (d) => d.span_minutes / 60), stroke: "var(--theme-foreground-muted)", strokeDasharray: "3,3" }),
    Plot.dot(nights, { x: (d) => d.span_minutes / 60, y: (d) => d.asleep_minutes / 60, r: 1.8, fill: "var(--theme-foreground-focus)", fillOpacity: 0.5, tip: true, channels: { night: (d) => d.date_str } }),
  ],
})
```

```js
const efficiency = d3.sum(nights, (d) => d.asleep_minutes) / d3.sum(nights, (d) => d.span_minutes);
```

```js
const noAwake = nights.filter((d) => d.span_minutes === d.asleep_minutes).length;
```

```js
display(
  htl.html`<p>Across every night, <b>${(100 * efficiency).toFixed(0)}%</b> of the time
    between falling asleep and getting up was scored as asleep. Read that as a
    statement about the band's sensitivity rather than about unusually unbroken sleep:
    it scored <i>no</i> awake minutes at all on
    <b>${((100 * noAwake) / nights.length).toFixed(0)}%</b> of nights, which is not
    plausible as a description of how people sleep. Brief awakenings are simply below
    what it detects. Nor is this sleep efficiency in the clinical sense, which counts
    from when you get into bed — the band cannot know that.</p>`
);
```
