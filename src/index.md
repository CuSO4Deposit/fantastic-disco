# cuso4d

Dashboards over [CPI](https://github.com/cuso4d/CPI), my access layer for personal
data exports. Everything is built from archived exports at build time; there is no
server and no data leaves the machine.

## Sources

<div class="grid grid-cols-2">
  <div class="card">
    <h3>Video</h3>
    <p>Watch history, searches and subscriptions from PipePipe.</p>
    <p>
      <a href="./video/">Overview</a> ·
      <a href="./video/fandoms">Fandoms</a> ·
      <a href="./video/raw">Raw</a>
    </p>
  </div>
</div>

## Reading these numbers

PipePipe keeps one history row per video and overwrites its timestamp on every
play, so an export knows only when each video was *last* watched. Anything derived
from that is a lower bound, and per-day charts stay absent until enough snapshots
have accumulated to place watches in time.
