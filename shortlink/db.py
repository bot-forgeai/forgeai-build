"""SQLite storage for shortlink: links and their click history."""
import random
import sqlite3
import string
import time

_ALPHABET = string.ascii_letters + string.digits


def connect(path):
    # ThreadingHTTPServer handles each request on its own thread, but a
    # single sqlite3 connection isn't safe to use concurrently from
    # multiple threads by default -- check_same_thread=False lifts sqlite's
    # own guard, and callers (see server.py) serialize access with a lock.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS links (
            code TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clicks (
            code TEXT NOT NULL,
            clicked_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _random_code(length=6):
    return "".join(random.choice(_ALPHABET) for _ in range(length))


def create_link(conn, url, code=None):
    """Insert a new link, generating a unique random code if none is given.

    Raises ValueError if an explicitly requested code is already taken.
    """
    if code:
        existing = conn.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
        if existing:
            raise ValueError(f"code {code!r} is already taken")
    else:
        # Collisions are astronomically unlikely at 6 chars of base62 but
        # retry a few times rather than trusting that blindly.
        for _ in range(10):
            candidate = _random_code()
            existing = conn.execute("SELECT 1 FROM links WHERE code = ?", (candidate,)).fetchone()
            if not existing:
                code = candidate
                break
        else:
            raise RuntimeError("could not generate a unique code after 10 attempts")

    conn.execute(
        "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
        (code, url, time.time()),
    )
    conn.commit()
    return code


def get_link(conn, code):
    row = conn.execute("SELECT url FROM links WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def record_click(conn, code):
    conn.execute("INSERT INTO clicks (code, clicked_at) VALUES (?, ?)", (code, time.time()))
    conn.commit()


def get_stats(conn, code):
    link = conn.execute(
        "SELECT url, created_at FROM links WHERE code = ?", (code,)
    ).fetchone()
    if link is None:
        return None
    url, created_at = link
    count, last = conn.execute(
        "SELECT COUNT(*), MAX(clicked_at) FROM clicks WHERE code = ?", (code,)
    ).fetchone()
    return {
        "code": code,
        "url": url,
        "created_at": created_at,
        "clicks": count,
        "last_clicked_at": last,
    }


def list_links(conn):
    """All links with their click counts, newest first."""
    rows = conn.execute(
        """
        SELECT links.code, links.url, links.created_at, COUNT(clicks.code)
        FROM links
        LEFT JOIN clicks ON clicks.code = links.code
        GROUP BY links.code
        ORDER BY links.created_at DESC
        """
    ).fetchall()
    return [
        {"code": code, "url": url, "created_at": created_at, "clicks": clicks}
        for code, url, created_at, clicks in rows
    ]
