"""Multi-file archive format for huffc.

Bundles several files into one container, each compressed independently
with the existing single-file format (so `format.compress`/`decompress`
stay the only place Huffman logic lives).

Layout:
    magic (5 bytes)         b"HUFA1"
    num_files (4 bytes, big-endian)
    per file:
        name_len (2 bytes, big-endian)
        name (name_len bytes, utf-8 -- a plain file's basename, or
              "<dirname>/<relative path>" for a file found while walking
              a directory input, always "/"-separated regardless of OS)
        blob_len (8 bytes, big-endian)
        blob (blob_len bytes -- a full huffc single-file container,
              i.e. whatever format.compress() returned)
"""

import os
import struct

from .format import compress, decompress

MAGIC = b"HUFA1"


class ArchiveError(Exception):
    pass


def pack_archive(paths):
    """Compress each file in `paths` and pack them into one archive blob.

    A plain file's entry name is just its basename (directory components
    are stripped). A directory in `paths` is walked recursively and its
    files are stored under "<dirname>/<relative path>" entry names,
    preserving that subtree's internal structure -- this is what lets a
    whole directory be archived without every file's basename needing to
    be globally unique, the collision case a flat file list can't avoid.
    """
    entries = _collect_entries(paths)
    out = bytearray(MAGIC)
    out += struct.pack(">I", len(entries))
    for path, name in entries:
        with open(path, "rb") as f:
            data = f.read()
        blob = compress(data)
        name_bytes = name.encode("utf-8")
        out += struct.pack(">H", len(name_bytes))
        out += name_bytes
        out += struct.pack(">Q", len(blob))
        out += blob
    return bytes(out)


def _collect_entries(paths):
    """Expand `paths` into a flat list of (source_path, arcname) pairs."""
    entries = []
    for path in paths:
        if os.path.isdir(path):
            base = os.path.basename(path.replace(os.sep, "/").rstrip("/")) or path
            for root, _dirs, files in sorted(os.walk(path)):
                for fname in sorted(files):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, path).replace(os.sep, "/")
                    entries.append((full, _validate_arcname(f"{base}/{rel}")))
        else:
            entries.append((path, _safe_name(path)))
    return entries


def unpack_archive(blob):
    """Return a list of (name, data) pairs for every file in an archive blob."""
    if blob[:5] != MAGIC:
        raise ArchiveError("not a huffc archive (bad magic)")

    pos = 5
    (num_files,) = struct.unpack_from(">I", blob, pos)
    pos += 4

    entries = []
    for _ in range(num_files):
        (name_len,) = struct.unpack_from(">H", blob, pos)
        pos += 2
        name = blob[pos : pos + name_len].decode("utf-8")
        pos += name_len
        _validate_arcname(name)
        (blob_len,) = struct.unpack_from(">Q", blob, pos)
        pos += 8
        file_blob = blob[pos : pos + blob_len]
        pos += blob_len
        entries.append((name, decompress(file_blob)))

    return entries


def _safe_name(path):
    name = os.path.basename(path.replace(os.sep, "/").rstrip("/"))
    if not name or name in (".", ".."):
        raise ArchiveError(f"unsafe or empty archive entry name for path: {path!r}")
    return name


def _validate_arcname(name):
    """Reject an archive entry name that could escape the extract dir."""
    parts = name.split("/")
    if not name or any(p in ("", ".", "..") for p in parts) or name.startswith("/"):
        raise ArchiveError(f"unsafe archive entry name: {name!r}")
    return name
