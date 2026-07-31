# cuso4d

Dashboards over [CPI](https://github.com/cuso4d/CPI), my access layer for personal
data exports. Everything is built from archived exports at build time; there is no
server and no data leaves the machine.

## Sources

```js
// Which sources exist is decided at build time by a loader, since a page cannot read
// the filesystem and Framework exposes no way to read the nav from one. A card
// pointing at pages a build never rendered would fail link validation.
const sources = FileAttachment("./data/sources.json").json();
```

```js
display(
  htl.html`<div class="grid grid-cols-2">
    ${sources.map(
      (s) => htl.html`<div class="card">
        <h3>${s.name}</h3>
        <p>${s.blurb}</p>
        <p>${s.pages.map(
          (p, i) => htl.html`${i ? " · " : ""}<a href="${`.${p.path}`}">${p.name}</a>`
        )}</p>
      </div>`
    )}
  </div>`
);
```

## Reading these numbers

The two sources store their data in opposite ways, and it changes what each can
answer.

PipePipe keeps one history row per video and overwrites its timestamp on every
play, so an export knows only when each video was *last* watched. Anything derived
from that is a lower bound, and per-day charts stay absent until enough snapshots
have accumulated to place watches in time.

Gadgetbridge appends instead: one immutable row per minute, so a single backup
already holds years of history and a per-day chart is sound. What it cannot fill in
is time the band never synced — it buffers about a week, then overwrites, so those
stretches are missing rather than empty and no later backup recovers them.
