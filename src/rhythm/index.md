---
theme: dashboard
title: Rhythm
---

# Rhythm games

Scores recorded by hand in [Y-Offline](https://github.com/CuSO4Deposit/Y-Offline), one
row per play. [Charts](./charts) is per-chart progress — what improved and what is being
ground without moving.

```js
const games = FileAttachment("./data/games.json").json();
```

```js
// Every game the build was configured for, in the loader's order. A game with no
// records at all comes through as null rather than being dropped, so it can be named
// as configured-but-unplayed instead of silently vanishing.
const played = Object.entries(games)
  .filter(([, g]) => g !== null)
  .map(([key, g]) => ({ key, ...g }));
const unplayed = Object.entries(games)
  .filter(([, g]) => g === null)
  .map(([key]) => key);
```

```js
// The unit every trend chart is drawn in. Both games rank their pools on a metric()
// the SDK computes, but the two are on different scales — Arcaea's is a 0-13 play
// potential, PJSK's a 5-33 level plus bonus — so they are never drawn on one axis.
const totals = {
  plays: d3.sum(played, (g) => g.activity.plays),
  charts: d3.sum(played, (g) => g.activity.charts),
  days: d3.sum(played, (g) => g.activity.active_days),
  sessions: d3.sum(played, (g) => g.activity.sessions.length),
};
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Plays recorded</h2>
    <span class="big">${totals.plays.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Charts touched</h2>
    <span class="big">${totals.charts.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Days played</h2>
    <span class="big">${totals.days.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Sittings</h2>
    <span class="big">${totals.sessions.toLocaleString()}</span>
  </div>
</div>

```js
// A JS block rather than an inline ${...}: an inline expression spanning blank lines
// ends the Markdown paragraph and the rest renders as literal source.
display(
  htl.html`<div class="note">
    Every rating here comes from each game's chart catalogue <b>as it stands today</b>,
    because a play record stores judgements and not a rating. Games rebalance charts, so
    a replayed history scores old plays with today's constants — these curves answer
    "what would my standing have been at each point, by today's numbers", not "what did
    the app show me back then". Nothing in a single database can recover the latter.
    ${played.every((g) => g.rating_basis === "current") ? "" : "Some series report a different basis."}
  </div>`
);
```

```js
if (unplayed.length > 0) {
  display(
    htl.html`<div class="warning">
      ${unplayed.join(", ")} ${unplayed.length === 1 ? "is" : "are"} configured but has
      no records for this player.
    </div>`
  );
}
```

```js
const breakTotal = d3.sum(played, (g) => d3.sum(g.breaks, (b) => b.days));
```

```js
if (breakTotal > 0) {
  const longest = d3.greatest(
    played.flatMap((g) => g.breaks.map((b) => ({ ...b, game: g.name }))),
    (b) => b.days
  );
  display(
    htl.html`<div class="warning">
      ${breakTotal.toLocaleString()} days fall inside a break of a month or more, the
      longest ${longest.days} days of ${longest.game} from ${longest.from}. The trend
      lines carry the last value across them — the pool really did hold, since nothing
      was played — so a flat stretch is an absence rather than a plateau.
    </div>`
  );
}
```

## Where each game stands

```js
display(
  htl.html`<div class="grid grid-cols-2">
    ${played.map(
      (g) => htl.html`<div class="card">
        <h2>${g.name}</h2>
        <span class="big">${g.current_average.toFixed(2)}</span>
        <p>mean ${g.metric_label.toLowerCase()} across the best
        ${g.activity.charts >= g.best_capacity ? g.best_capacity : g.activity.charts}
        charts — ${g.metric_note}. ${g.activity.plays.toLocaleString()} plays on
        ${g.activity.charts.toLocaleString()} charts over
        ${g.activity.active_days.toLocaleString()} days.</p>
      </div>`
    )}
  </div>`
);
```

## Standing over time

```js
// One chart per game rather than one shared axis: the metrics are on different scales
// and mean different things, so a single y axis would invite reading one against the
// other. Faceting would do the same. Each gets the full width.
for (const g of played) {
  // Arcaea's headline number is the v7.0 formula: the best 50 with its top 10 counted
  // twice, and the pool alone is the whole rule — there is no recent pool to churn it.
  // No other game here has a number distinct from its pool average, so the rest plot
  // the pool average directly.
  const potential = g.potential ?? [];
  const series = potential.length
    ? potential.map((p) => ({ at: new Date(p.at * 1000), value: p.potential, full: p.b50_size >= g.best_capacity }))
    : g.trend.map((p) => ({ at: new Date(p.at * 1000), value: p.average, full: p.full }));
  // Before the pool fills, the average is over however many slots are occupied, so it
  // is not comparable with what comes after. Drawn faintly rather than dropped.
  const filling = series.filter((d) => !d.full);
  const full = series.filter((d) => d.full);
  display(
    Plot.plot({
      title: `${g.name} — ${potential.length ? "potential" : g.metric_label.toLowerCase()}`,
      subtitle: `${series.length.toLocaleString()} plays that moved the number${filling.length ? `; the first ${filling.length} are over a pool still filling and not comparable with the rest` : ""}`,
      width,
      height: 300,
      x: { label: null, type: "utc" },
      y: { label: g.metric_label, grid: true, nice: true },
      marks: [
        // Breaks marked so a flat run is legible as absence. Dates are anchored at UTC
        // midnight to match the utc axis; parsing "2024-07-04" alone would land a day
        // earlier for anyone east of UTC.
        Plot.rect(g.breaks, {
          x1: (b) => new Date(`${b.from}T00:00:00Z`),
          x2: (b) => new Date(`${b.to}T00:00:00Z`),
          fill: "var(--theme-foreground-faintest)",
        }),
        Plot.lineY(filling, { x: "at", y: "value", stroke: "var(--theme-foreground-faint)", strokeWidth: 1 }),
        Plot.lineY(full, { x: "at", y: "value", stroke: "var(--theme-foreground-focus)", strokeWidth: 2 }),
        Plot.tip(full, Plot.pointerX({ x: "at", y: "value", format: { y: (d) => d.toFixed(3) } })),
      ],
    })
  );
}
```

## The ceiling

```js
// Mean accuracy per chart rating is where a skill ceiling shows for Arcaea. It does not
// for PJSK — see below — so both are drawn and the difference is stated rather than
// assumed. Bands with too few charts are noise; the SDK reports `charts` per band.
const MIN_BAND_CHARTS = 4;
```

```js
for (const g of played) {
  const bands = g.bands.filter((b) => b.charts >= MIN_BAND_CHARTS);
  const dropped = g.bands.length - bands.length;
  display(
    Plot.plot({
      title: `${g.name} — accuracy by chart rating`,
      subtitle: `bands of at least ${MIN_BAND_CHARTS} charts${dropped ? `; ${dropped} sparser bands left out` : ""}. Bars are mean accuracy over every play, points the best single play.`,
      width,
      height: 280,
      x: { label: "Chart rating →", tickFormat: (d) => `${d}` },
      // percent: true multiplies before the scale, so the domain belongs in percent
      // space. Pinned low rather than at zero: everything here sits above 95% and a
      // zero baseline would flatten the whole range into the top 5% of the axis.
      y: { label: "Accuracy", grid: true, percent: true, domain: [d3.min(bands, (b) => b.mean_accuracy) * 100 - 1, 100.5] },
      marks: [
        Plot.barY(bands, { x: "rating", y: "mean_accuracy", fill: "var(--theme-foreground-focus)", tip: true }),
        Plot.dot(bands, { x: "rating", y: "best_accuracy", r: 2.5, fill: "var(--theme-foreground)" }),
      ],
    })
  );
}
```

```js
// AP rate per band, which is where PJSK's ceiling actually lives: its accuracy barely
// moves across the whole range while the share of charts ever fully cleared collapses.
for (const g of played) {
  const bands = g.bands.filter((b) => b.charts >= MIN_BAND_CHARTS);
  display(
    Plot.plot({
      title: `${g.name} — charts fully cleared, by rating`,
      subtitle: "share of charts in each band with at least one all-perfect play",
      width,
      height: 260,
      x: { label: "Chart rating →", tickFormat: (d) => `${d}` },
      y: { label: "Charts with an AP", grid: true, percent: true, domain: [0, 100] },
      marks: [
        Plot.barY(bands, { x: "rating", y: (b) => b.ap_charts / b.charts, fill: "var(--theme-foreground-focus)", tip: true }),
        Plot.ruleY([0]),
      ],
    })
  );
}
```

```js
const excluded = d3.sum(played, (g) => d3.sum(g.bands, (b) => b.excluded_plays));
const implausible = d3.sum(played, (g) => g.implausible.length);
```

```js
display(
  htl.html`<p>Nothing validates a record after it is typed, so a mistyped judgement
    would sit in the database and quietly poison the averages above rather than raise
    anything. The SDK checks each play against what its judgements can possibly mean:
    <b>${implausible.toLocaleString()}</b> plays here are impossible and
    <b>${excluded.toLocaleString()}</b> were excluded from a band on that basis. Bands
    report their own exclusions, so a band computed from fewer plays than it claims says
    so.</p>`
);
```

## How the playing is distributed

```js
const sessions = played.flatMap((g) =>
  g.activity.sessions.map((s) => ({ ...s, game: g.name }))
);
```

```js
Plot.plot({
  title: "Plays per sitting",
  subtitle: `${sessions.length.toLocaleString()} sittings across every game; a sitting ends after 30 minutes without a play`,
  width,
  height: 260,
  x: { label: "Plays in one sitting →" },
  y: { label: "Sittings", grid: true },
  color: { legend: true },
  marks: [
    Plot.rectY(sessions, Plot.binX({ y: "count" }, { x: "plays", fill: "game", thresholds: d3.range(1, 32, 2) })),
    Plot.ruleY([0]),
  ],
})
```

```js
Plot.plot({
  title: "When a sitting starts",
  subtitle: `local hour in ${played[0].timezone}, taken from when each sitting began`,
  width,
  height: 260,
  x: { label: "Hour of day →", domain: d3.range(24), tickFormat: (d) => `${d}` },
  y: { label: "Sittings", grid: true },
  color: { legend: true },
  marks: [
    Plot.barY(sessions, Plot.groupX({ y: "count" }, { x: "hour", fill: "game" })),
    Plot.ruleY([0]),
  ],
})
```

An hour here is when a sitting *began*, and it is the entry time rather than the play
time: `y ... add` stamps a record with the clock as it is typed, and its `--back` flag
shifts a backfilled play by whole days while keeping that time of day. So this reads as
when scores get entered, which for same-session entry is also when they were played.

## Judgements

Each judgement is a share of what it can actually be a share of, which is not one number.
Most are outcomes of a note, so they divide by every note played and partition it exactly.
A *sub-judgement* divides something else: Arcaea's `max_pure` counts how many of the pure
notes were perfectly timed, so its denominator is `pure` — a note that was not pure never
had the chance to be max_pure. Dividing both kinds by one total would count every pure
note twice.

```js
const judgements = played.flatMap((g) =>
  g.judgements.map((j) => ({
    game: g.name,
    // Prefixed with the game, because a bar's category is its identity: two rows
    // landing on one band draw over each other and silently show only one.
    label: `${g.name} · ${j.name}`,
    ...j,
  }))
);
const topLevel = judgements.filter((j) => !j.is_subdivision);
const subdivisions = judgements.filter((j) => j.is_subdivision);
// Every top-level judgement except each game's best one. That bar carries 97-99% of the
// notes, so on a shared axis it pins everything else to nothing — and it is the least
// interesting of them, since where the losses come from is the question.
const bestPerGame = new Set(
  played.map((g) => {
    const top = d3.greatest(g.judgements.filter((j) => !j.is_subdivision), (j) => j.share);
    return `${g.name} · ${top.name}`;
  })
);
const rare = topLevel.filter((j) => !bestPerGame.has(j.label));
```

```js
// Notes rather than judgements: `basis` on any top-level judgement is the note total,
// which is the same number for all of them within a game. Taken from the first rather
// than summed, since summing would count every note once per judgement.
const notesPerGame = played.map((g) => ({
  game: g.name,
  notes: g.judgements.find((j) => !j.is_subdivision)?.basis ?? 0,
  plays: g.activity.plays,
}));
const notesTotal = d3.sum(notesPerGame, (n) => n.notes);
```

<div class="grid grid-cols-3">
  <div class="card">
    <h2>Notes ever hit</h2>
    <span class="big">${notesTotal.toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Notes per play</h2>
    <span class="big">${Math.round(notesTotal / d3.sum(notesPerGame, (n) => n.plays)).toLocaleString()}</span>
  </div>
  <div class="card">
    <h2>Notes missed outright</h2>
    <span class="big">${d3.sum(judgements.filter((j) => !j.is_subdivision && (j.name === "lost" || j.name === "miss")), (j) => j.count).toLocaleString()}</span>
  </div>
</div>

```js
display(
  htl.html`<p>${notesPerGame
    .map((n) => `${n.game}: ${n.notes.toLocaleString()} notes across ${n.plays.toLocaleString()} plays`)
    .join("; ")}. Every note is counted once per play, so a chart replayed ten times
    contributes its length ten times — this is how many notes were <i>hit</i>, not how
    many distinct notes exist in the charts played.</p>`
);
```

```js
Plot.plot({
  title: "How every note was hit",
  subtitle: "share of all notes played, within each game. These partition the notes, so each game's shares sum to 100%.",
  width,
  height: 300,
  marginLeft: 170,
  // Linear, with the rare judgements carried by a label rather than by bar length.
  // A log axis is what this wants — `perfect` at 99.5% against `bad` at 0.0055% is
  // four orders of magnitude — but a bar spans from an implicit x1 of 0, and 0 does
  // not exist on a log scale, so every bar silently vanishes. Dots would survive it;
  // bars are the better read here, so the axis gives way instead.
  x: { label: "Share of notes", grid: true, percent: true, domain: [0, 100] },
  y: { label: null },
  marks: [
    Plot.barX(topLevel, {
      x: "share",
      y: "label",
      fill: "game",
      sort: { y: "x", reverse: true },
      tip: true,
      channels: { count: "count", of: "basis_name", outOf: "basis" },
    }),
    // The share as text, because the small ones are invisible as bars at this scale
    // and they are the interesting ones — where the losses actually come from.
    Plot.text(topLevel, {
      x: "share",
      y: "label",
      text: (j) => (j.share >= 0.01 ? `${(100 * j.share).toFixed(1)}%` : `${(100 * j.share).toFixed(3)}%`),
      dx: 6,
      textAnchor: "start",
      fill: "var(--theme-foreground-muted)",
    }),
    Plot.ruleX([0]),
  ],
})
```

```js
// The rare judgements on their own log axis, where three orders of magnitude are
// legible. Dots rather than bars: a bar spans from an implicit x1 of 0 and a log scale
// has no zero, so bars vanish silently — which is exactly what went wrong when this
// chart was first written.
//
// A judgement that never happened would break the axis too, so those are dropped and
// named below instead. Today none are zero, but an all-clean stretch would make `lost`
// or `bad` zero and take the whole chart down with it.
const rarePositive = rare.filter((j) => j.count > 0);
const rareZero = rare.filter((j) => j.count === 0);
```

```js
if (rarePositive.length > 0) {
  display(
    Plot.plot({
      title: "The same shares, log scale",
      subtitle: `where the losses come from. Each game's best judgement is left out — at 97-99% it pins everything else to the axis.`,
      width,
      height: 240,
      marginLeft: 170,
      x: {
        label: "Share of notes (log scale)",
        grid: true,
        type: "log",
        percent: true,
        domain: [
          d3.min(rarePositive, (j) => j.share) * 100 / 2,
          d3.max(rarePositive, (j) => j.share) * 100 * 2,
        ],
      },
      y: { label: null },
      marks: [
        Plot.ruleY(rarePositive, {
          y: "label",
          x1: () => (d3.min(rarePositive, (r) => r.share) * 100) / 2,
          x2: (j) => j.share * 100,
          stroke: "var(--theme-foreground-faint)",
        }),
        Plot.dot(rarePositive, {
          x: "share",
          y: "label",
          fill: "game",
          r: 5,
          sort: { y: "x", reverse: true },
          tip: true,
          channels: { count: "count", of: "basis_name", outOf: "basis" },
        }),
      ],
    })
  );
}
```

```js
if (rareZero.length > 0) {
  display(
    htl.html`<p>Never recorded at all, so absent from the log chart above:
      ${rareZero.map((j) => `${j.game} ${j.name}`).join(", ")}.</p>`
  );
}
```

```js
if (subdivisions.length > 0) {
  display(
    Plot.plot({
      title: "Sub-judgements, against the judgement they subdivide",
      subtitle: subdivisions
        .map((j) => `${j.name} is a share of ${j.basis_name}`)
        .join("; "),
      width,
      height: 140,
      marginLeft: 170,
      x: { label: "Share of the parent judgement", grid: true, percent: true, domain: [0, 100] },
      y: { label: null },
      marks: [
        Plot.barX(subdivisions, {
          x: "share",
          y: "label",
          fill: "game",
          sort: { y: "x", reverse: true },
          tip: true,
          channels: { count: "count", of: "basis_name", outOf: "basis" },
        }),
        Plot.ruleX([0]),
      ],
    })
  );
}
```

```js
display(
  htl.html`<p>${subdivisions
    .map(
      (j) =>
        `${j.count.toLocaleString()} of ${j.basis.toLocaleString()} ${j.basis_name} notes in ${j.game} were ${j.name} (${(100 * j.share).toFixed(1)}%)`
    )
    .join("; ")} — that is the bonus carrying an all-perfect Arcaea play from 100% to
    101%, not a fourth way to hit a note.</p>`
);
```

