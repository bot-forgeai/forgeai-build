"""Newline-delimited-JSON TCP transport connecting real raftlite node processes.

Connection setup avoids duplicate links between the same pair of nodes: the
node with the *lower* id always connects out to the node with the higher id,
and the higher-id node only accepts. Whichever side opens the socket sends a
HELLO frame identifying itself, so the peer end knows which node_id this
particular socket belongs to.

A one-shot client request (PUT/GET) skips the HELLO handshake entirely: it
opens a connection, sends one line, reads one line back, and disconnects.
"""
import json
import socket
import threading
import time


def send_line(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def read_lines(sock):
    buf = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line:
                yield json.loads(line.decode("utf-8"))


class PeerLink:
    """One open, bidirectional connection to a single peer node."""

    def __init__(self, peer_id, sock):
        self.peer_id = peer_id
        self.sock = sock
        self.lock = threading.Lock()

    def send(self, msg):
        with self.lock:
            try:
                send_line(self.sock, msg)
                return True
            except OSError:
                return False

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Transport:
    """Owns the listening socket, peer connections, and client request
    handling for one raftlite node. Delivers incoming Raft messages to
    `on_peer_message(sender_id, msg)` and client requests to
    `on_client_request(msg) -> response_dict`.
    """

    def __init__(self, node_id, bind_address, peer_addresses,
                 on_peer_message, on_client_request):
        self.node_id = node_id
        self.bind_address = bind_address
        self.peer_addresses = dict(peer_addresses)  # peer_id -> (host, port)
        self.on_peer_message = on_peer_message
        self.on_client_request = on_client_request

        self.links = {}  # peer_id -> PeerLink
        self.links_lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = []

    def start(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(self.bind_address)
        listener.listen(16)
        self._listener = listener

        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        self._threads.append(t)

        for peer_id, addr in self.peer_addresses.items():
            if peer_id < self.node_id:
                t = threading.Thread(target=self._connect_loop, args=(peer_id, addr), daemon=True)
                t.start()
                self._threads.append(t)

    def stop(self):
        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass
        with self.links_lock:
            for link in self.links.values():
                link.close()

    def send(self, dest_id, msg):
        with self.links_lock:
            link = self.links.get(dest_id)
        if link is None:
            return False
        return link.send(msg)

    def _register_link(self, peer_id, sock):
        link = PeerLink(peer_id, sock)
        with self.links_lock:
            old = self.links.get(peer_id)
            self.links[peer_id] = link
        if old is not None:
            old.close()
        t = threading.Thread(target=self._reader_loop, args=(link,), daemon=True)
        t.start()
        self._threads.append(t)

    def _reader_loop(self, link):
        try:
            for msg in read_lines(link.sock):
                self.on_peer_message(link.peer_id, msg)
        except OSError:
            pass

    def _connect_loop(self, peer_id, addr):
        while not self._stop.is_set():
            try:
                sock = socket.create_connection(addr, timeout=2)
                sock.settimeout(None)  # the timeout above is for connect() only;
                # ongoing reads must block indefinitely, or an idle gap longer
                # than it (e.g. a slow election) kills the reader thread.
                send_line(sock, {"type": "HELLO", "node_id": self.node_id})
                self._register_link(peer_id, sock)
                return
            except OSError:
                time.sleep(0.5)

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            t = threading.Thread(target=self._handle_incoming, args=(conn,), daemon=True)
            t.start()
            self._threads.append(t)

    def _handle_incoming(self, conn):
        f = conn.makefile("rwb")
        try:
            line = f.readline()
            if not line:
                return
            msg = json.loads(line.decode("utf-8"))
            if msg.get("type") == "HELLO":
                self._register_link(msg["node_id"], conn)
                return
            # One-shot client request.
            response = self.on_client_request(msg)
            send_line(conn, response)
            conn.close()
        except OSError:
            pass


def client_request(address, msg, timeout=2.0):
    """Send a single PUT/GET request to a node and return its response dict."""
    with socket.create_connection(address, timeout=timeout) as sock:
        send_line(sock, msg)
        sock.settimeout(timeout)
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("connection closed before a response was received")
            buf += chunk
        line, _ = buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))
