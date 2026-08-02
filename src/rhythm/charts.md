---
theme: dashboard
title: Charts
---

# Per-chart progress

What actually improved, chart by chart, and what is being replayed without moving. Every
figure is over plays of the same chart at the same difficulty — a song's Master and
Expert charts are separate rows, because they are separate charts.

```js
const games = FileAttachment("./data/games.json").json();
```

```js
const played = Object.entries(games)
  .filter(([, g]) => g !== null)
  .map(([key, g]) => ({ key, ...g }));
const game = view(
  Inputs.select(played, {
    label: "Game",
    format: (g) => g.name,
    value: played[0],
  })
);
```

```js
// Charts with at least two plays; the loader filters on that already, since `gain` is
// best-minus-first and a single play has no gain to report.
const progress = game.progress;
// A label unique by construction. Two different songs can share a name across
// difficulties, and a bar's category is its identity: rows sharing a y value land in one
// band and draw over each other, showing one and silently dropping the other. Truncating
// a long title would create that collision where none existed, so the difficulty rides
// along and nothing is cut.
const labelled = progress.map((c) => ({
  ...c,
  label: `${c.name} · ${c.difficulty ?? c.rating_class}`,
}));
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Charts replayed</h2>
    <span class="big">${progress.length.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Charts touched once</h2>
    <span class="big">${(game.activity.charts - progress.length).toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Median plays</h2>
    <span class="big">${d3.median(progress, (c) => c.plays).toFixed(1)}</span>
  </div>
  <div class="card">
    <h2>Most plays</h2>
    <span class="big">${d3.max(progress, (c) => c.plays).toLocaleString()}</span>
  </div>
</div>

## What improved most

```js
const TOP = 25;
const topGain = d3.sort(labelled, (c) => -c.gain).slice(0, TOP);
```

```js
Plot.plot({
  title: `Largest gain in ${game.metric_label.toLowerCase()}`,
  subtitle: `top ${TOP} of ${progress.length.toLocaleString()} replayed charts, best play minus first play`,
  width,
  height: 620,
  marginLeft: 260,
  x: { label: `Gain in ${game.metric_label.toLowerCase()} →`, grid: true },
  y: { label: null },
  marks: [
    Plot.barX(topGain, {
      x: "gain",
      y: "label",
      fill: "var(--theme-foreground-focus)",
      sort: { y: "x", reverse: true },
      tip: true,
    }),
    Plot.ruleX([0]),
  ],
})
```

```js
display(
  htl.html`<p>A large gain means the first attempt was poor, not that the chart is now
    strong — it is the distance travelled. The metric is ${game.metric_note}.</p>`
);
```

## What is not moving

```js
const stalled = d3.sort(labelled, (c) => -c.stalled_plays).slice(0, TOP);
```

```js
Plot.plot({
  title: "Plays since the personal best",
  subtitle: `top ${TOP} by plays that did not improve anything. A chart high here is being ground without yielding.`,
  width,
  height: 620,
  marginLeft: 260,
  x: { label: "Plays since the best one →", grid: true },
  y: { label: null },
  marks: [
    Plot.barX(stalled, {
      x: "stalled_plays",
      y: "label",
      fill: "var(--theme-foreground-focus)",
      sort: { y: "x", reverse: true },
      tip: true,
    }),
    Plot.ruleX([0]),
  ],
})
```

## Plays against what they bought

```js
Plot.plot({
  title: "Does replaying a chart pay?",
  subtitle: `${progress.length.toLocaleString()} charts. Each point is one chart: how many times it was played against how much its ${game.metric_label.toLowerCase()} rose.`,
  width,
  height: 320,
  x: { label: "Plays of this chart →", grid: true },
  y: { label: `Gain in ${game.metric_label.toLowerCase()}`, grid: true },
  marks: [
    Plot.dot(labelled, {
      x: "plays",
      y: "gain",
      r: 2.5,
      fill: "var(--theme-foreground-focus)",
      fillOpacity: 0.6,
      channels: { chart: "label" },
      tip: true,
    }),
    Plot.ruleY([0]),
  ],
})
```

```js
// Spearman rather than Pearson: the question is whether more plays go with more gain at
// all, and both are skewed — a handful of charts carry many more plays than the rest.
const rank = (values) => {
  const order = d3.sort(d3.range(values.length), (i) => values[i]);
  const ranks = new Array(values.length);
  order.forEach((idx, position) => (ranks[idx] = position));
  return ranks;
};
const rx = rank(progress.map((c) => c.plays));
const ry = rank(progress.map((c) => c.gain));
const mx = d3.mean(rx);
const my = d3.mean(ry);
const spearman =
  d3.sum(rx, (v, i) => (v - mx) * (ry[i] - my)) /
  Math.sqrt(d3.sum(rx, (v) => (v - mx) ** 2) * d3.sum(ry, (v) => (v - my) ** 2));
```

```js
display(
  htl.html`<p>Rank correlation between plays and gain is
    <b>${spearman.toFixed(2)}</b> across ${progress.length.toLocaleString()} charts.
    Read it as a description of how this player has spent their attempts rather than as
    a rule about practice: a chart gets replayed <i>because</i> the first attempt left
    something on the table, so plays and gain are not independent to begin with.</p>`
);
```

## Best accuracy against best score

```js
Plot.plot({
  title: "Where accuracy and the pool metric disagree",
  subtitle: "peak accuracy need not come from the same play as the best metric, and a harder chart scores higher at the same accuracy",
  width,
  height: 320,
  x: { label: "Best accuracy →", grid: true, percent: true },
  y: { label: `Best ${game.metric_label.toLowerCase()}`, grid: true },
  marks: [
    Plot.dot(labelled, {
      x: "best_accuracy",
      y: "best_metric",
      r: 2.5,
      fill: "var(--theme-foreground-focus)",
      fillOpacity: 0.6,
      channels: { chart: "label" },
      tip: true,
    }),
  ],
})
```

## Every replayed chart

```js
const search = view(Inputs.search(labelled, { placeholder: "Search charts…" }));
```

```js
Inputs.table(search, {
  columns: ["name", "difficulty", "plays", "gain", "best_metric", "best_accuracy", "stalled_plays", "last_at"],
  header: {
    name: "Chart",
    difficulty: "Difficulty",
    plays: "Plays",
    gain: "Gain",
    best_metric: `Best ${game.metric_label.toLowerCase()}`,
    best_accuracy: "Best accuracy",
    stalled_plays: "Since best",
    last_at: "Last played",
  },
  format: {
    gain: (d) => d.toFixed(2),
    best_metric: (d) => d.toFixed(2),
    best_accuracy: (d) => `${(100 * d).toFixed(2)}%`,
    // Sliced from an ISO string at UTC, not read off a Date: getDate and friends
    // convert to the browser's zone, which is not where these were played.
    last_at: (d) => new Date(d * 1000).toISOString().slice(0, 10),
  },
  sort: "gain",
  reverse: true,
})
```
