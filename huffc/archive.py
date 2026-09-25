"""Multi-file archive format for huffc.

Bundles several files into one container, each compressed independently
with the existing single-file format (so `format.compress`/`decompress`
stay the only place Huffman logic lives).

Layout:
    magic (5 bytes)         b"HUFA1"
    num_files (4 bytes, big-endian)
    per file:
        name_len (2 bytes, big-endian)
        name (name_len bytes, utf-8, just the input path's basename --
              no directory components are stored)
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

    Entry names are just each path's basename (directory components are
    always stripped), so extracting never writes outside the target
    directory and duplicate basenames from different directories collide.
    """
    out = bytearray(MAGIC)
    out += struct.pack(">I", len(paths))
    for path in paths:
        with open(path, "rb") as f:
            data = f.read()
        blob = compress(data)
        name = _safe_name(path)
        name_bytes = name.encode("utf-8")
        out += struct.pack(">H", len(name_bytes))
        out += name_bytes
        out += struct.pack(">Q", len(blob))
        out += blob
    return bytes(out)


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
