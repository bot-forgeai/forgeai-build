"""Incremental rebuilds: poll content/templates/static for changes and rebuild."""
import os
import threading

from .build import build_site


def scan_signature(dirs):
    """Return a dict of {path: mtime} across every file in the given dirs.

    Missing directories are skipped (e.g. a site with no static/ dir).
    Comparing two signatures for equality is how change detection works --
    it catches additions, deletions, and content changes alike.
    """
    signature = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for name in files:
                path = os.path.join(root, name)
                try:
                    signature[path] = os.path.getmtime(path)
                except OSError:
                    pass
    return signature


def watch_loop(content_dir, templates_dir, output_dir, static_dir=None, site_title="My Site",
                base_url=None, drafts=False, poll_interval=1.0, stop_event=None,
                sleep_fn=None, on_build=None):
    """Rebuild once, then poll for source changes and rebuild again on each change.

    Runs until stop_event is set. sleep_fn defaults to time.sleep but can be
    swapped for a fake in tests, e.g. one that mutates a source file and sets
    stop_event after a fixed number of calls, so tests never need a real clock.
    """
    if stop_event is None:
        stop_event = threading.Event()
    if sleep_fn is None:
        import time
        sleep_fn = time.sleep

    watched_dirs = [content_dir, templates_dir, static_dir]

    pages = build_site(content_dir, templates_dir, output_dir, static_dir, site_title,
                        base_url, drafts)
    if on_build:
        on_build(pages)
    signature = scan_signature(watched_dirs)

    while not stop_event.is_set():
        sleep_fn(poll_interval)
        if stop_event.is_set():
            break
        new_signature = scan_signature(watched_dirs)
        if new_signature != signature:
            signature = new_signature
            pages = build_site(content_dir, templates_dir, output_dir, static_dir, site_title,
                                base_url, drafts)
            if on_build:
                on_build(pages)

    return pages
