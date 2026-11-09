"""Offline guard for the workbook bridge process.

Import this module FIRST, before anything that might touch the network
(huggingface_hub, transformers, mlx_lm). It does two things:

1. Sets the Hugging Face offline environment variables so model loading only
   ever reads from the local cache and never checks for updates.
2. Patches the socket layer so this Python process can only open connections
   to loopback (127.0.0.1 / ::1 / localhost) and Unix sockets. Any other
   outbound connection raises OfflineViolation.

An optional allowlist of hostnames can be passed to install(). Only those
exact hostnames are allowed to resolve and connect (used for the optional
weather lookup). The default allowlist is empty, meaning fully offline.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import threading

for _var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE",
             "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
    os.environ[_var] = "1"

# Never route through a proxy. A proxy running on localhost would otherwise
# look like a loopback connection and slip past the guard below.
for _var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_var, None)
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "*"


class OfflineViolation(ConnectionRefusedError):
    pass


_LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}
_lock = threading.Lock()
_allow_hosts: set[str] = set()
_allowed_ips: set[str] = set()
_blocked: list[str] = []          # recent blocked attempts, for /health
_installed = False

_orig_getaddrinfo = socket.getaddrinfo
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex


def _is_loopback(host: str) -> bool:
    if host in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _record(what: str) -> None:
    with _lock:
        _blocked.append(what)
        del _blocked[:-20]


def _guarded_getaddrinfo(host, *args, **kwargs):
    h = host.decode() if isinstance(host, bytes) else (host or "")
    if _is_loopback(h):
        return _orig_getaddrinfo(host, *args, **kwargs)
    if h.lower() in _allow_hosts:
        results = _orig_getaddrinfo(host, *args, **kwargs)
        with _lock:
            for r in results:
                _allowed_ips.add(r[4][0])
        return results
    _record(f"dns:{h}")
    raise OfflineViolation(f"Offline mode: blocked lookup of '{h}'")


def _check_addr(sock, address) -> None:
    if sock.family == getattr(socket, "AF_UNIX", None):
        return
    host = address[0] if isinstance(address, tuple) else str(address)
    if _is_loopback(host):
        return
    with _lock:
        if host in _allowed_ips:
            return
    _record(f"connect:{host}")
    raise OfflineViolation(f"Offline mode: blocked connection to {host}")


def _guarded_connect(self, address):
    _check_addr(self, address)
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    _check_addr(self, address)
    return _orig_connect_ex(self, address)


def install(allow_hosts: list[str] | None = None) -> None:
    """Activate the guard. Safe to call again to change the allowlist."""
    global _installed
    with _lock:
        _allow_hosts.clear()
        _allowed_ips.clear()
        _allow_hosts.update(h.lower().strip() for h in (allow_hosts or []) if h.strip())
    if not _installed:
        socket.getaddrinfo = _guarded_getaddrinfo
        socket.socket.connect = _guarded_connect
        socket.socket.connect_ex = _guarded_connect_ex
        _installed = True


def status() -> dict:
    with _lock:
        return {
            "active": _installed,
            "allow_hosts": sorted(_allow_hosts),
            "recent_blocked": list(_blocked),
        }
