"""Content-addressable object storage: blobs, trees, commits.

Every object is stored under .vcslite/objects/<sha[:2]>/<sha[2:]>,
zlib-compressed, as `b"<type> <size>\\0<content>"` — the same framing
git itself uses, chosen because it lets hashing and storage stay
type-agnostic (the header alone tells a reader how to decode the body).
"""
import hashlib
import os
import zlib


def hash_object(data: bytes, obj_type: str) -> str:
    header = f"{obj_type} {len(data)}\0".encode()
    full = header + data
    return hashlib.sha1(full).hexdigest()


def _object_path(repo_dir: str, sha: str) -> str:
    return os.path.join(repo_dir, "objects", sha[:2], sha[2:])


def write_object(repo_dir: str, data: bytes, obj_type: str) -> str:
    sha = hash_object(data, obj_type)
    path = _object_path(repo_dir, sha)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        header = f"{obj_type} {len(data)}\0".encode()
        with open(path, "wb") as f:
            f.write(zlib.compress(header + data))
    return sha


def read_object(repo_dir: str, sha: str) -> tuple[str, bytes]:
    path = _object_path(repo_dir, sha)
    if not os.path.exists(path):
        raise KeyError(f"no such object: {sha}")
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
    header, _, body = raw.partition(b"\0")
    obj_type, _, _size = header.decode().partition(" ")
    return obj_type, body


def object_exists(repo_dir: str, sha: str) -> bool:
    return os.path.exists(_object_path(repo_dir, sha))
