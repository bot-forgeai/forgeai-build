import os


def dispatch(store, request):
    """Apply one decoded JSON request dict to a KVStore, return a response dict.

    Pure dispatch logic shared by the socket server and its tests, kept
    separate from any actual socket I/O so it can be tested directly
    against an in-memory KVStore.
    """
    op = request.get("op")

    if op == "put":
        store.put(request["key"], request["value"])
        return {"ok": True}

    if op == "get":
        key = request["key"]
        if key not in store:
            return {"ok": False, "error": f"no such key {key!r}"}
        return {"ok": True, "value": store.get(key)}

    if op == "delete":
        key = request["key"]
        if not store.delete(key):
            return {"ok": False, "error": f"no such key {key!r}"}
        return {"ok": True}

    if op == "keys":
        return {"ok": True, "keys": store.keys()}

    if op == "dump":
        return {"ok": True, "items": store.items()}

    if op == "prefix":
        return {"ok": True, "items": store.prefix(request["prefix"])}

    if op == "range":
        items = store.range(request.get("start"), request.get("end"))
        return {"ok": True, "items": items}

    if op == "compact":
        before = os.path.getsize(store.path) if os.path.exists(store.path) else 0
        store.compact()
        after = os.path.getsize(store.path) if os.path.exists(store.path) else 0
        return {"ok": True, "before": before, "after": after, "count": len(store)}

    return {"ok": False, "error": f"unknown op {op!r}"}
