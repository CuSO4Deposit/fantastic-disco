---
theme: dashboard
title: Rating
---

# What moved the rating

Arcaea's v7.0 potential is a best-50 pool with its top ten counted twice. A play enters
only by beating the pool's weakest entry, so once the pool is full the number can only
rise — every raise below is one score that did it, and the value it moved the potential
from and to. The [Overview](./) draws the curve; this is what bends it.

The same caveat as everywhere else applies: a play record stores judgements, not a
rating, so old plays are scored with the catalogue **as it stands today**. This is "what
would have happened by today's constants", not what the app showed at the time.

```js
const rating = FileAttachment("./data/rating.json").json()
```

```js
const moves = rating?.moves ?? []
// Parsing the offset-bearing string is safe — it names an absolute instant — but every
// date and time *shown* is sliced from the string, never read off the resulting Date:
// getHours and toISOString would convert to the browser's zone, which is not where the
// play happened.
const rows = moves.map((m) => ({ ...m, at: new Date(m.at_local) }))
const raises = rows.filter((m) => m.delta > 0)
// The first move the full pool could not fall below. It need not be a raise — the last
// empty slot can be taken by a weak play, which lowers the average.
const settled = rows.find((m) => m.full) ?? null
const current = rows.length ? rows[rows.length - 1].to : null
// A pool that is still filling moves by whole points when a slot is taken, so the
// largest gain on the page is always one of those, not a play beating the pool. The
// question "what was the biggest single raise" only has an answer confined to plays
// made with the pool already full, where the gain is capped by what the play displaced.
const fullRaises = raises.filter((m) => m.full_before)
const biggest = d3.greatest(fullRaises, (m) => m.delta)
```

```js
// Shared by the two step charts so their tooltips cannot drift apart.
const moveTitle = (m) =>
  `${m.name} · ${m.difficulty}\n${m.score_before === null ? "" : `${m.score_before.toLocaleString()} → `}${m.score.toLocaleString()}\n${m.from.toFixed(4)} → ${m.to.toFixed(4)} (+${m.delta.toFixed(4)})${m.score_before === null ? "" : `\n${m.plays_since_best} plays over ${m.days_since_best.toFixed(1)}d since the last best`}`
```

```js
if (rating === null) {
  display(
    htl.html`<div class="warning">
      Arcaea is not configured for this build, so there is no potential timeline to show.
    </div>`
  )
}
```

```js
// A JS block rather than inline ${...}: the card is conditional, and an inline
// expression spanning lines ends the Markdown paragraph and renders the rest as source.
if (rating !== null) {
  display(
    htl.html`<div class="grid grid-cols-4">
      <div class="card">
        <h2>Current potential</h2>
        <span class="big">${current === null ? "—" : current.toFixed(4)}</span>
      </div>
      <div class="card">
        <h2>Plays that raised it</h2>
        <span class="big">${raises.length.toLocaleString()}</span>
      </div>
      <div class="card">
        <h2>Largest raise, full pool</h2>
        <span class="big">${biggest ? `+${biggest.delta.toFixed(4)}` : "—"}</span>
        ${biggest ? htl.html`<p>${biggest.name} · ${biggest.difficulty}</p>` : ""}
      </div>
      <div class="card">
        <h2>Pool full since</h2>
        <span class="big">${settled ? settled.at_local.slice(0, 10) : "not yet"}</span>
        <p>${settled ? "from here only a better score can raise the number" : "every play still adds a slot"}</p>
      </div>
    </div>`
  )
}
```

## The climb

Like GitHub's contribution view, one year at a time — a year's moves spread across the
full width instead of being squeezed into a strip beside every other year.

```js
// Two and a half years on one axis squeezes each into a band too narrow to read, so the
// line and the calendar both show a single chosen year. `years` comes from the loader's
// offset-bearing dates, so it is the recording zone's calendar, not the browser's.
const years = [...new Set(rows.map((m) => m.at_local.slice(0, 4)))].sort()
```

```js
// A cell of its own, and not nested in a conditional: `view` only wires the input up as
// a view at the top level of a block. Wrapped in a ternary it still draws the select, but
// returns undefined, and every cell below is fed a year that matches nothing.
const year = view(Inputs.select(years, { label: "Year", value: years[years.length - 1] }))
```

```js
const yearRows = year ? rows.filter((m) => m.at_local.startsWith(year)) : []
const yearRaises = yearRows.filter((m) => m.delta > 0)
const yearStart = year ? new Date(`${year}-01-01T00:00:00Z`) : null
const yearEnd = year ? new Date(`${Number(year) + 1}-01-01T00:00:00Z`) : null
// The level carried into the year: the last move before it. Without this the line would
// start at the year's first move and hide where the year began.
const carry = year ? (rows.filter((m) => m.at < yearStart).at(-1) ?? null) : null
const series = year ? [{ at: yearStart, to: carry ? carry.to : 0 }, ...yearRows] : []
```

```js
// GitHub's layout: columns are weeks, rows are weekdays, one cell per day. Colour is the
// number of raises that day rather than their size — a single play moves the pool by
// whole points while it is filling, which would drown out every later day. The gain is
// in the tooltip.
if (year) {
  const firstSunday = d3.utcSunday.floor(yearStart)
  const perDay = d3.rollup(
    yearRaises,
    (v) => v.length,
    (m) => m.at_local.slice(0, 10)
  )
  const cells = d3.utcDay.range(yearStart, yearEnd).map((d) => ({
    at: d,
    week: Math.floor(d3.utcDay.count(firstSunday, d) / 7),
    weekday: d.getUTCDay(),
    count: perDay.get(d.toISOString().slice(0, 10)) ?? 0
  }))
  display(
    Plot.plot({
      title: `${year} — days the potential moved`,
      subtitle: "one cell per day; a blank day had no raise. Weeks run left to right, Sunday on top.",
      width,
      height: 170,
      // Both axes are band scales, so each needs the full ordered domain rather than an
      // extent — a two-number domain would be read as two categories. Weekday 0 is
      // Sunday, listed first so it sits at the top as in GitHub's view.
      x: { axis: null, domain: d3.range(0, d3.max(cells, (d) => d.week) + 1) },
      y: { axis: null, domain: d3.range(0, 7) },
      color: { scheme: "greens", label: "Raises" },
      marks: [
        Plot.cell(cells, {
          x: "week",
          y: "weekday",
          fill: "count",
          inset: 0.5,
          tip: true,
          channels: { day: "at" }
        })
      ]
    })
  )
}
```

```js
// Plot has no zoom mark, so d3-zoom drives an explicit x domain and the chart is rebuilt
// around it — wheel or pinch to zoom, drag to pan, double-click to zoom in. The y domain
// is recomputed from the visible span on every rebuild: pinning it to the whole year would
// leave a zoomed-in day looking flat, which is the very thing being fixed.
const zoomableX = (render, { full, width, height }) => {
  const container = document.createElement("div")
  const fullScale = d3.scaleUtc().domain(full).range([0, width])
  let transform = d3.zoomIdentity
  let applying = false
  const zoom = d3
    .zoom()
    .scaleExtent([1, 500])
    .extent([
      [0, 0],
      [width, height]
    ])
    .translateExtent([
      [0, 0],
      [width, height]
    ])
    .on("zoom", (event) => {
      if (applying) return
      transform = event.transform
      update()
    })
  function update() {
    const [start, end] = [fullScale.invert(transform.invertX(0)), fullScale.invert(transform.invertX(width))]
    const svg = render([start, end])
    d3.select(svg).call(zoom)
    applying = true
    d3.select(svg).call(zoom.transform, transform)
    applying = false
    container.replaceChildren(svg)
  }
  update()
  return container
}
```

```js
if (year) {
  display(
    zoomableX(
      (domain) => {
        const inView = series.filter((d) => d.at >= domain[0] && d.at <= domain[1])
        const carry = d3.greatest(
          series.filter((d) => d.at < domain[0]),
          (d) => d.at
        )
        const next = series.find((d) => d.at > domain[1])
        const values = [...(carry ? [carry.to] : []), ...inView.map((d) => d.to), ...(next ? [next.to] : [])]
        const [lo, hi] = d3.extent(values.length ? values : [0, 1])
        const pad = lo === hi ? 0.01 : (hi - lo) * 0.1
        return Plot.plot({
          title: `${rating?.name ?? "Arcaea"} — potential in ${year}`,
          subtitle: "wheel or pinch to zoom the time axis, drag to pan; the vertical range follows what is in view",
          width,
          height: 640,
          x: { label: null, type: "utc", domain },
          y: { label: rating?.metric_label ?? "Play potential", grid: true, domain: [lo - pad, hi + pad] },
          marks: [
            Plot.lineY(series, {
              x: "at",
              y: "to",
              stroke: "var(--theme-foreground-muted)",
              strokeWidth: 1,
              curve: "step-after"
            }),
            Plot.dot(yearRaises, { x: "at", y: "to", r: 2, fill: "var(--theme-foreground-focus)" }),
            Plot.tip(yearRaises, Plot.pointerX({ x: "at", y: "to", title: moveTitle }))
          ]
        })
      },
      { full: [yearStart, yearEnd], width, height: 640 }
    )
  )
}
```

Before the pool fills, the number is the mean over however many slots are occupied, so a
rise is partly a slot being taken by a chart the pool did not previously hold — the
repertoire effect [Practice](./practice) separates out. Only after it is full does a
raise mean a score beat one already in the pool.

## Usual level, not the best

The rating above is a pool of personal bests, so it only ever rises and says nothing
about an ordinary night. This is every play instead, each measured against its own
chart's median, then rolled over a window and trimmed — the same per-play form the
[Practice](./practice) page averages by month, with the high and low tails cut off.
Unlike the rating, it can fall.

```js
const plays = rating?.plays ?? []
// The loader's delta is a fraction of accuracy; percentage points read better on the axis.
const playRows = plays.map((p) => ({ ...p, at: new Date(p.at_local), pct: p.delta * 100 }))
```

```js
const windowPlays = view(Inputs.range([20, 400], { label: "Window (plays)", value: 120, step: 10 }))
```

```js
const trim = view(Inputs.range([0, 40], { label: "Trim each end (%)", value: 10, step: 1 }))
```

```js
// A centred rolling trimmed mean, over plays in time order rather than by clock: a window
// of plays stays statistically stable whether or not the player was active that month.
// Only interior points are kept, so the ends are not a half-window of edge bias.
const smoothed = (() => {
  const n = playRows.length
  const half = Math.floor(windowPlays / 2)
  const out = []
  for (let i = half; i < n - half; i++) {
    const values = playRows
      .slice(i - half, i + half + 1)
      .map((p) => p.pct)
      .sort((a, b) => a - b)
    const cut = Math.floor((values.length * trim) / 100)
    const kept = values.slice(cut, values.length - cut)
    if (kept.length < 5) continue
    out.push({ at: playRows[i].at, at_local: playRows[i].at_local, value: d3.mean(kept) })
  }
  return out
})()

// The axis is pinned to the line, not to the raw plays: one collapse can sit far below the
// rest, and letting that set the extent flattens the line being read. The scattered plays
// are still drawn, clipped to the frame.
const level = smoothed.map((d) => d.value)
const levelPad = Math.max(0.05, (d3.max(level) - d3.min(level)) * 0.15)
```

```js
if (smoothed.length) {
  display(
    Plot.plot({
      title: "Usual level over time",
      subtitle: `each play is its accuracy above its own chart's median; the line is the mean over a ${windowPlays}-play window with the top and bottom ${trim}% dropped`,
      width,
      height: 340,
      x: { label: null, type: "utc" },
      y: {
        label: "Accuracy vs the chart's median (pp)",
        grid: true,
        domain: [d3.min(level) - levelPad, d3.max(level) + levelPad]
      },
      marks: [
        Plot.ruleY([0], { stroke: "var(--theme-foreground-muted)" }),
        Plot.dot(playRows, {
          x: "at",
          y: "pct",
          r: 1,
          fill: "var(--theme-foreground-faint)",
          fillOpacity: 0.15,
          clip: true
        }),
        Plot.lineY(smoothed, { x: "at", y: "value", stroke: "var(--theme-foreground-focus)", strokeWidth: 2 }),
        Plot.tip(smoothed, Plot.pointerX({ x: "at", y: "value", format: { y: (d) => d.toFixed(3) } }))
      ]
    })
  )
}
```

```js
if (smoothed.length) {
  const first = smoothed[0]
  const last = smoothed[smoothed.length - 1]
  display(
    htl.html`<p>${playRows.length.toLocaleString()} plays on charts with at least three
      records — a chart with fewer has no stable median to sit against. Faint dots are
      single plays; the line is the trimmed mean, which is the only thing on this page
      that can fall. Between ${first.at_local.slice(0, 10)} and ${last.at_local.slice(0, 10)}
      it went from ${first.value.toFixed(3)} to ${last.value.toFixed(3)}pp.</p>`
  )
}
```

## Every raise

```js
// A JS block rather than inline ${...}: the sentence is conditional and spans lines,
// and a multi-line inline expression ends the Markdown paragraph.
if (rating !== null) {
  display(
    htl.html`<p>Newest first. ${raises.length === 0 ? "No play has raised the number yet." : `${raises.length.toLocaleString()} plays took it from ${raises[0].from.toFixed(4)} to ${current.toFixed(4)}, an overall gain of ${(current - raises[0].from).toFixed(4)}.`}</p>`
  )
}
```

```js
if (rating !== null) {
  display(
    Inputs.table(raises.slice().reverse(), {
      columns: [
        "at_local",
        "name",
        "difficulty",
        "score_before",
        "score",
        "days_since_best",
        "plays_since_best",
        "play_ptt",
        "from",
        "to",
        "delta"
      ],
      header: {
        at_local: "When",
        name: "Score",
        difficulty: "Difficulty",
        score_before: "Score before",
        score: "Score after",
        days_since_best: "Days since PB",
        plays_since_best: "Plays since PB",
        play_ptt: "Play potential",
        from: "Potential before",
        to: "Potential after",
        delta: "Gain"
      },
      format: {
        // Sliced from the loader's offset-bearing ISO string, never read off a Date.
        at_local: (d) => d.slice(0, 16).replace("T", " "),
        score_before: (d) => (d === null ? "—" : d.toLocaleString()),
        score: (d) => d.toLocaleString(),
        days_since_best: (d) => (d === null ? "—" : d >= 1 ? `${d.toFixed(1)}d` : `${(d * 24).toFixed(1)}h`),
        plays_since_best: (d) => (d === null ? "—" : d.toLocaleString()),
        play_ptt: (d) => d.toFixed(4),
        from: (d) => d.toFixed(4),
        to: (d) => d.toFixed(4),
        delta: (d) => `+${d.toFixed(4)}`
      }
    })
  )
}
```

```js
// A JS block rather than inline ${...}: the note spans lines and names the zone.
if (rating !== null) {
  display(
    htl.html`<p>Times are in ${rating.timezone}, sliced from the loader's offset-bearing
      strings. A pool can also dip while it fills — a weak play taking an empty slot —
      and those plays are not listed here; the <a href="./practice">Practice</a> page
      covers the filling.</p>`
  )
}
```
