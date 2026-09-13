import json
import socketserver
import threading

from .protocol import dispatch
from .store import KVStore


class KVRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        for raw_line in self.rfile:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                response = {"ok": False, "error": "invalid JSON request"}
            else:
                with self.server.lock:
                    try:
                        response = dispatch(self.server.store, request)
                    except KeyError as exc:
                        response = {"ok": False, "error": f"missing field {exc}"}
            self.wfile.write((json.dumps(response) + "\n").encode())


class KVServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server exposing a KVStore over a newline-delimited
    JSON request/response protocol.

    A single KVStore instance is shared across all connections/threads,
    guarded by one lock — the store's own file object and in-memory dict
    are not safe for concurrent access on their own.
    """

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, db_path):
        self.store = KVStore(db_path)
        self.lock = threading.Lock()
        super().__init__(addr, KVRequestHandler)

    def server_close(self):
        super().server_close()
        self.store.close()


def serve(host, port, db_path):
    server = KVServer((host, port), db_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()
