"""Minimal Polaris REST client shared by the toolbox scripts. Python 3.8+, standard library only.

Configuration (flags win over environment):
  POLARIS_URL     base URL of the install, e.g. https://polaris.example.com
  POLARIS_TOKEN   an API token (Server Settings -> API Tokens), sent as a bearer token
  --token-file    read the token from a file instead (keeps it out of shell history)
  --insecure      skip TLS verification (a lab install with a self-signed certificate)

A token is bound to a role: give it only the permissions the script needs (each script's
--help says which). Bearer requests need no CSRF token.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import uuid
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

# The scripts print em dashes and arrows; a Windows console on a legacy code page would
# mangle them. UTF-8 output, never an exception, wherever the interpreter allows it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


class PolarisError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def add_connection_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--url", default=os.environ.get("POLARIS_URL"), help="Polaris base URL (or POLARIS_URL)")
    p.add_argument("--token-file", help="file holding the API token (default: POLARIS_TOKEN)")
    p.add_argument("--insecure", action="store_true", help="do not verify the server's TLS certificate")


class Client:
    def __init__(self, url: str, token: str, insecure: bool = False):
        if not url:
            sys.exit("Set POLARIS_URL or pass --url.")
        if not token:
            sys.exit("Set POLARIS_TOKEN or pass --token-file.")
        self.base = url.rstrip("/") + "/api/v1"
        self.token = token.strip()
        self.ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Client":
        token = os.environ.get("POLARIS_TOKEN", "")
        if args.token_file:
            with open(args.token_file, encoding="utf-8") as f:
                token = f.read()
        return cls(args.url, token, args.insecure)

    def _send(self, method: str, path: str, data: Optional[bytes], content_type: Optional[str]) -> Tuple[int, Any, bytes]:
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Accept", "application/json")
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=120) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            status = e.code
        except urllib.error.URLError as e:
            raise PolarisError(0, f"cannot reach {self.base}: {e.reason}")
        body: Any = None
        if raw:
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                body = None
        if status >= 400:
            msg = body.get("error") if isinstance(body, dict) else raw.decode("utf-8", "replace")[:300]
            raise PolarisError(status, str(msg))
        return status, body, raw

    def get(self, path: str) -> Any:
        return self._send("GET", path, None, None)[1]

    def get_raw(self, path: str) -> bytes:
        return self._send("GET", path, None, None)[2]

    def post(self, path: str, body: Any) -> Any:
        return self._send("POST", path, json.dumps(body).encode("utf-8"), "application/json")[1]

    def put(self, path: str, body: Any) -> Any:
        return self._send("PUT", path, json.dumps(body).encode("utf-8"), "application/json")[1]

    def upload(self, path: str, field: str, filename: str, content: bytes, fields: dict) -> Any:
        """multipart/form-data POST: one file plus plain text fields."""
        boundary = "----polaris" + uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            if v is None:
                continue
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: text/plain\r\n\r\n".encode("utf-8") + content + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        return self._send("POST", path, b"".join(parts), f"multipart/form-data; boundary={boundary}")[1]
