---
theme: dashboard
title: Practice
---

# Repertoire or skill?

A best-30 pool keeps one record per chart and a play only enters by beating the weakest.
So once it fills, **the average can never fall** — verified on this data: zero decreases
after the pool filled, in either game. Every dip on the [overview](./) curve happens
while the pool is still filling up.

That makes potential a running total of the best thirty things ever done, not a reading
of how well you play now. It rises whenever a harder chart is attempted for the first
time, no improvement required. This page separates the two.

```js
const practice = FileAttachment("./data/practice.json").json();
```

```js
const played = Object.entries(practice)
  .filter(([, g]) => g !== null)
  .map(([key, g]) => ({ key, ...g }));
```

```js
// Anchored at UTC to match every `type: "utc"` axis below. Reading clock fields off a
// Date would convert to the browser's zone, which is not where these were played.
const asRows = (g) =>
  g.deflated.map((p) => ({ ...p, at: new Date(p.at * 1000) }));
```

## The deflator

Each game's pool metric is a chart rating plus a function of accuracy. So the pool
average splits *exactly* into the mean rating of the charts holding a slot, and how far
above their ratings they were played. The first is repertoire. The second is execution —
a difficulty-neutral index, needing no external baseline.

```js
// A JS block rather than an inline ${...} spanning lines: a multi-line inline
// expression ends the Markdown paragraph and the remainder renders as literal source.
display(
  htl.html`<div class="grid grid-cols-2">
    ${played.map((g) => {
      const s = g.deflated_summary;
      const share = s.average_change === 0 ? 0 : s.rating_change / s.average_change;
      return htl.html`<div class="card">
        <h2>${g.name}</h2>
        <span class="big">${(100 * share).toFixed(0)}% borrowed</span>
        <p>The pool average rose <b>${s.average_change >= 0 ? "+" : ""}${s.average_change.toFixed(3)}</b>
        over ${s.points.toLocaleString()} plays. Of that,
        <b>${s.rating_change >= 0 ? "+" : ""}${s.rating_change.toFixed(3)}</b> is harder
        charts entering the pool and
        <b>${s.bonus_change >= 0 ? "+" : ""}${s.bonus_change.toFixed(3)}</b> is playing
        the same difficulty better.</p>
      </div>`;
    })}
  </div>`
);
```

```js
// One chart per game: the two metrics are on different scales, so a shared axis would
// invite reading one against the other.
for (const g of played) {
  const rows = asRows(g);
  // Long form, because `stroke` names a column: two marks with separate y channels
  // would need two legends and could not share one colour scale.
  const long = rows.flatMap((p) => [
    { at: p.at, value: p.average, series: "pool average (nominal)" },
    { at: p.at, value: p.mean_rating, series: "mean chart rating (difficulty)" },
  ]);
  display(
    Plot.plot({
      title: `${g.name} — how much of the number is difficulty`,
      subtitle:
        "the gap between the lines is the accuracy component; a rise in the lower line is repertoire, not skill",
      width,
      height: 300,
      x: { label: null, type: "utc" },
      y: { label: g.metric_label, grid: true, nice: true },
      color: { legend: true, domain: ["pool average (nominal)", "mean chart rating (difficulty)"], range: ["var(--theme-foreground-focus)", "var(--theme-foreground-muted)"] },
      marks: [
        Plot.areaY(rows, {
          x: "at",
          y1: "mean_rating",
          y2: "average",
          fill: "var(--theme-foreground-focus)",
          fillOpacity: 0.12,
          curve: "step-after",
        }),
        Plot.lineY(long, { x: "at", y: "value", stroke: "series", strokeWidth: 2, curve: "step-after" }),
      ],
    })
  );
}
```

```js
// The execution half on its own axis. Plotted separately because it moves by tenths
// while the nominal average moves by whole points — on one axis it reads as flat.
for (const g of played) {
  const rows = asRows(g);
  display(
    Plot.plot({
      title: `${g.name} — the difficulty-neutral index`,
      subtitle: `mean ${g.metric_label.toLowerCase()} minus mean chart rating. Flat means the rise above was entirely difficulty.`,
      width,
      height: 240,
      x: { label: null, type: "utc" },
      y: { label: "Accuracy component", grid: true, nice: true },
      marks: [
        Plot.lineY(rows, { x: "at", y: "bonus", stroke: "var(--theme-foreground-focus)", strokeWidth: 2, curve: "step-after" }),
        Plot.tip(rows, Plot.pointerX({ x: "at", y: "bonus", format: { y: (d) => d.toFixed(3) } })),
      ],
    })
  );
}
```

## The same charts, played again

The deflator divides difficulty out of the pool. The other way to ask is to hold the
charts themselves fixed: take only charts played both before and after a midpoint, and
compare. Repertoire growth then cannot contribute at all.

```js
display(
  htl.html`<div class="grid grid-cols-2">
    ${played.map((g) => {
      const b = g.basket;
      const significant = b.p_value < 0.05;
      return htl.html`<div class="card">
        <h2>${g.name}</h2>
        <span class="big">${b.mean_gain >= 0 ? "+" : ""}${b.mean_gain.toFixed(3)}</span>
        <p>mean gain across <b>${b.charts}</b> charts played in both halves,
        <b>${b.improved}</b> up against <b>${b.declined}</b> down.
        ${significant
          ? htl.html`Sign test <b>p = ${b.p_value < 0.0001 ? b.p_value.toExponential(1) : b.p_value.toFixed(4)}</b> — a real gain.`
          : htl.html`Sign test <b>p = ${b.p_value.toFixed(3)}</b>, which is not distinguishable from noise.`}</p>
      </div>`;
    })}
  </div>`
);
```

```js
Plot.plot({
  title: "Execution gain on a fixed basket of charts",
  subtitle: "attempt counts matched per chart — see below for why that is not optional",
  width,
  height: 200,
  marginLeft: 120,
  x: { label: "Mean gain in the pool metric →", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(played, { x: (g) => g.basket.mean_gain, y: "name", fill: "var(--theme-foreground-focus)", tip: true }),
    Plot.ruleX([0]),
  ],
})
```

Attempt counts have to be matched, and it is not a refinement: `max()` over a window
rises with the number of plays in it, so whichever half holds more attempts wins for
free. Each chart contributes `n = min(early, late)` plays sampled from both sides and
averaged over many draws. On this data the unmatched version reached the opposite
conclusion for one of the two games.

## What has never been attempted

Every other figure on this site starts from plays, so a chart nobody touched is
invisible to all of them. This is the exception — and it is the supply side of the
inflation: a pool average can keep climbing for as long as unplayed charts remain within
reach.

```js
display(
  htl.html`<div class="grid grid-cols-2">
    ${played.map(
      (g) => htl.html`<div class="card">
        <h2>${g.name}</h2>
        <span class="big">${g.untouched_total.toLocaleString()}</span>
        <p>charts rated ${g.untouched_floor.toFixed(1)} or above with no record at all,
        out of a ${g.catalogue_charts.toLocaleString()}-chart catalogue. The hardest ever
        played is ${g.hardest_played.toFixed(1)}.</p>
      </div>`
    )}
  </div>`
);
```

```js
for (const g of played) {
  display(
    Plot.plot({
      title: `${g.name} — hardest charts never played`,
      subtitle: `top ${g.untouched.length} of ${g.untouched_total.toLocaleString()} unattempted at ${g.untouched_floor.toFixed(1)}+`,
      width,
      height: 520,
      marginLeft: 230,
      x: { label: "Chart rating →", grid: true, domain: [g.untouched_floor - 0.2, d3.max(g.untouched, (c) => c.rating) + 0.2] },
      y: { label: null },
      marks: [
        Plot.barX(g.untouched, {
          x: "rating",
          // A label unique by construction: two charts of one song differ only by
          // difficulty, and rows sharing a y value would collapse into one band.
          y: (c) => `${c.name} · ${c.difficulty ?? c.rating_class}`,
          fill: "var(--theme-foreground-focus)",
          sort: { y: "x", reverse: true },
          tip: true,
        }),
        Plot.ruleX([g.untouched_floor - 0.2]),
      ],
    })
  );
}
```

## Exploring, then grinding

```js
const discovery = played.flatMap((g) =>
  g.discovery.map((m) => ({ ...m, game: g.name, month: new Date(`${m.month}-01T00:00:00Z`) }))
);
```

```js
Plot.plot({
  title: "Share of plays that were a chart's first ever",
  subtitle: "months with no play are absent rather than zero — a gap is a hiatus, not a month of pure repetition",
  width,
  height: 280,
  x: { label: null, type: "utc" },
  y: { label: "New charts", grid: true, percent: true, domain: [0, 100] },
  color: { legend: true },
  marks: [
    Plot.dot(discovery, { x: "month", y: "new_share", stroke: "game", r: (d) => Math.sqrt(d.plays), fillOpacity: 0.2, fill: "game", tip: true, channels: { plays: "plays", new: "new_charts" } }),
    Plot.lineY(discovery, { x: "month", y: "new_share", stroke: "game", strokeWidth: 1.5 }),
    Plot.ruleY([0]),
  ],
})
```

Point size is the number of plays that month. Both games start out mostly exploring and
settle into replaying a known set — which is what makes the pool average slow down
rather than any change in skill. A late bump is a game being picked back up after a
break.

## Within a sitting

```js
const positions = played.flatMap((g) =>
  g.positions.map((p) => ({ ...p, game: g.name }))
);
```

```js
Plot.plot({
  title: "Is the first play of a sitting cold or fresh?",
  subtitle: "accuracy minus that chart's own median, so which charts get played first does not confound it",
  width,
  height: 280,
  x: { label: "Position in the sitting →", tickFormat: (d) => `${d}` },
  y: { label: "Accuracy vs chart median", grid: true, percent: true },
  color: { legend: true },
  marks: [
    Plot.ruleY([0], { stroke: "var(--theme-foreground-muted)" }),
    Plot.lineY(positions, { x: "position", y: "mean_delta", stroke: "game", strokeWidth: 2 }),
    Plot.dot(positions, { x: "position", y: "mean_delta", fill: "game", r: (d) => Math.sqrt(d.plays) / 2, tip: true, channels: { plays: "plays" } }),
  ],
})
```

The two games disagree, and that is the finding rather than a wrinkle. Arcaea's opening
play is its best and it declines from there — a fatigue effect. Project SEKAI's opening
play is its *worst*, improving after — a warm-up effect. The last position is a pooled
bucket, so it holds long sittings rather than being one position.

Both effects are small in absolute terms: fractions of a percentage point of accuracy.
They are visible at all only because each play is measured against its own chart's
median rather than against the average play.
