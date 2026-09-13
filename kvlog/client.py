import json
import socket


class RemoteError(Exception):
    """Raised when a kvlog server rejects a request or the connection fails."""


def send_request(host, port, request, timeout=5.0):
    """Send one request dict to a kvlog server, return its decoded response dict."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((json.dumps(request) + "\n").encode())
        f = sock.makefile("r")
        line = f.readline()
    if not line:
        raise RemoteError("no response from server")
    return json.loads(line)


def call(host, port, op, **fields):
    """Send a request built from op/fields, raise RemoteError on failure,
    otherwise return the response dict."""
    response = send_request(host, port, {"op": op, **fields})
    if not response.get("ok"):
        raise RemoteError(response.get("error", "unknown error"))
    return response
