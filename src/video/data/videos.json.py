"""Every video PipePipe knows about, with watch info attached where it exists.

One row per video rather than per watch record, so the page can ask about things
history alone cannot see — saved and never played, pushed by a subscription and
skipped past. `watched` is None for those.
"""

import json
import sys
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

import fandoms
from _shared import SERVICE_NAMES, blocked_uploaders, exports
from cuso4d import pipepipe as pp


def main() -> None:
    archive = exports()
    blocked = blocked_uploaders()

    watched = {r.stream.key: r for r in pp.watched(archive)}
    in_playlist: dict[tuple[int, str], list[str]] = {}
    for entry in pp.playlists(archive):
        in_playlist.setdefault(entry.stream.key, []).append(entry.playlist_name or "")
    from_feed = {e.stream.key: e.subscription.name for e in pp.feed(archive)}
    subscribed = {s.name for s in pp.subscriptions(archive)}

    rows = []
    excluded = 0
    for stream in pp.streams(archive):
        if stream.uploader in blocked:
            excluded += 1
            continue
        record = watched.get(stream.key)
        duration = stream.duration
        rows.append(
            {
                "service": SERVICE_NAMES.get(stream.service_id, str(stream.service_id)),
                "url": stream.url,
                "title": stream.title,
                "uploader": stream.uploader,
                "subscribed": stream.uploader in subscribed,
                "fandoms": fandoms.tags(stream.title, stream.uploader),
                "type": stream.stream_type,
                # None for live streams, where the column is a placeholder.
                "duration_s": duration.total_seconds() if duration else None,
                "view_count": stream.view_count,
                "uploaded": (
                    stream.upload_date.isoformat() if stream.upload_date else None
                ),
                "uploaded_is_approximate": stream.upload_date_is_approximate,
                "playlists": in_playlist.get(stream.key, []),
                "feed_from": from_feed.get(stream.key),
                "watched": (
                    None
                    if record is None
                    else {
                        "last": record.last_watched.isoformat(),
                        "repeats": record.repeat_count,
                        "progress": record.progress_ratio,
                        "marked_only": record.marked_only,
                    }
                ),
            }
        )

    json.dump(
        {
            # Reported so pages can say totals are partial rather than quietly
            # differing from the archive.
            "excluded": excluded,
            # Emitted rather than hardcoded in the page: the group names are local
            # configuration, and a page that spelled them out would put them back
            # into the repo.
            "groups": list(fandoms.groups()),
            "videos": rows,
        },
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
