"""What was kept rather than passed through: bookmarks and downloads.

The two are opposites in what they can be trusted for.

Bookmarks are present state read from each machine's newest snapshot. Deleting one
leaves no tombstone without Sync, so this is what is bookmarked now and says nothing
about what ever was. `date_added` is also not when something was found: an import or a
profile restore writes the time of the import, which shows up here as a few thousand
bookmarks added in the same second.

Downloads accumulate across snapshots because Firefox both expires the annotations and
keys them per page, so re-downloading a URL overwrites the earlier record. Only the
filename is emitted, never the destination path: that path is local and carries the
account name.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import firefox as ff
from urls import extension_of, filename_of, site_of


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_FIREFOX_EXPORTS", "Firefox places.sqlite snapshots")

    # Visit counts by (machine, url), to answer which bookmarks were ever opened.
    # Firefox's own `visit_count` is used rather than counting visit rows: a page
    # dropped by expiration and revisited restarts at 1 either way, and this at least
    # agrees with what the browser shows.
    visited: dict[tuple[str, str], int] = {}
    for page in ff.pages(archive):
        visited[page.key] = page.visit_count

    folders: defaultdict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    bookmarks = []
    separators = 0
    folder_rows = 0

    for bookmark in ff.bookmarks(archive):
        kind = bookmark.type
        if kind is ff.BookmarkType.FOLDER:
            folder_rows += 1
            continue
        if kind is ff.BookmarkType.SEPARATOR:
            separators += 1
            continue
        if bookmark.url is None:
            # Documented as always set for a bookmark; skipped rather than trusted.
            continue

        folders[(bookmark.snapshot.host, bookmark.path)] += 1
        bookmarks.append(
            {
                "machine": bookmark.snapshot.host,
                "site": site_of(bookmark.url),
                "title": bookmark.title,
                "folder": "/".join(bookmark.path) or "(root)",
                "root": bookmark.root,
                # Local date, so it lines up with the daily charts elsewhere.
                "added": bookmark.date_added.astimezone(tz).date().isoformat(),
                # Full timestamp too: the interesting fact about these dates is how
                # many share one second, which a date alone hides.
                "added_at": bookmark.date_added.astimezone(tz).isoformat(),
                "modified": bookmark.last_modified.astimezone(tz).date().isoformat(),
                "visits": visited.get((bookmark.snapshot.host, bookmark.url), 0),
            }
        )

    if not bookmarks and not folder_rows:
        sys.exit("no bookmarks in the archive; refusing to emit an empty library")

    downloads = []
    for download in ff.downloads(archive):
        name = filename_of(download.destination) if download.destination else None
        downloads.append(
            {
                "machine": download.snapshot.host,
                "site": site_of(download.url),
                # The basename only. The rest of the path names the account.
                "filename": name,
                "extension": extension_of(name) if name else "(none)",
                "bytes": download.file_size,
                "added": download.date_added.astimezone(tz).date().isoformat(),
                # Whether the file was later removed from disk, or None when the
                # metadata annotation is missing — two of 84 in the reference archive.
                "deleted": download.deleted,
                "state": download.state_raw,
            }
        )

    json.dump(
        {
            "timezone": str(tz),
            "bookmarks": bookmarks,
            "downloads": downloads,
            "folders": [
                {
                    "machine": machine,
                    "folder": "/".join(path) or "(root)",
                    "depth": len(path),
                    "bookmarks": count,
                }
                for (machine, path), count in sorted(
                    folders.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ],
            # Folder and separator rows, which are bookmark rows too but not bookmarks.
            "folder_rows": folder_rows,
            "separators": separators,
        },
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
