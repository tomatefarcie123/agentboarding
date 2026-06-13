"""x402 reference rail — the agent-payable trial endpoint the vendor does NOT
yet expose. Protocol-faithful HTTP 402 flow (Coinbase x402 / HTTP-402 pattern):

    agent GETs the resource with no payment
        -> 402 Payment Required + a payment-required descriptor (price, scope,
           expiry, nonce)
    agent presents a payment mandate referencing the descriptor
        -> server SETTLES IN TEST MODE (no real funds move) and returns a
           scoped, single-use, capped, auto-expiring GRANT
    the grant releases a pre-funded, duration-capped capability so the re-run
    agent can boot ONE real device.

Money-trap (mirrors the auth-trap): the agent NEVER receives a reusable payment
instrument — only a scoped one-time grant. The human pre-authorizes a budget
once. The test-mode settle is labeled as such and never presented as a real
payment. AP2 (Google) / ACP (Stripe·OpenAI) are heavier protocol alternates.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional


@dataclass
class Grant:
    grant_id: str
    scope: str
    max_run_duration: int          # minutes — capped
    expires_at: float
    single_use: bool = True
    used: bool = False
    settle_mode: str = "test"      # NEVER "live" in this reference rail
    # Deliberately NO reusable payment instrument here (no card, no token).
    capability: str = "boot-one-device"

    def to_dict(self) -> Dict:
        return {
            "grant_id": self.grant_id, "scope": self.scope,
            "max_run_duration": self.max_run_duration, "expires_at": self.expires_at,
            "single_use": self.single_use, "used": self.used,
            "settle_mode": self.settle_mode, "capability": self.capability,
        }


class X402Rail:
    """Core protocol logic, decoupled from HTTP so it is unit-testable directly.
    `now` is injectable so expiry can be tested without sleeping."""

    def __init__(self, price: str = "$0.05", scope: str = "one cloud device",
                 ttl_seconds: int = 120, max_run_duration: int = 30,
                 now: Callable[[], float] = time.time):
        self.price = price
        self.scope = scope
        self.ttl_seconds = ttl_seconds
        self.max_run_duration = max_run_duration
        self._now = now
        self._descriptors: Dict[str, Dict] = {}
        self._grants: Dict[str, Grant] = {}
        self._counter = 0

    def _next(self, prefix: str) -> str:
        self._counter += 1
        seed = f"{prefix}-{self._counter}-{self._now()}".encode()
        return f"{prefix}_{hashlib.sha256(seed).hexdigest()[:16]}"

    def payment_required(self) -> Dict:
        """The 402 body: a payment-required descriptor."""
        nonce = self._next("nonce")
        descriptor = {
            "x402Version": 1,
            "accepts": [{
                "scheme": "exact",
                "price": self.price,
                "currency": "USD",
                "scope": self.scope,
                "maxRunDurationMinutes": self.max_run_duration,
                "expiresInSeconds": self.ttl_seconds,
                "nonce": nonce,
                "payTo": "genymotion-cloud-reference-rail (TEST MODE)",
            }],
            "note": "Agent-payable trial endpoint (reference rail). Settle is TEST MODE — no real funds move.",
        }
        self._descriptors[nonce] = descriptor
        return descriptor

    def settle(self, mandate: Dict) -> Grant:
        """TEST-MODE settle of a payment mandate -> a scoped single-use grant."""
        nonce = (mandate or {}).get("nonce")
        if nonce not in self._descriptors:
            raise ValueError("unknown or missing descriptor nonce in mandate")
        if mandate.get("mode") == "live":
            raise ValueError("reference rail refuses live settle; TEST MODE only")
        grant = Grant(
            grant_id=self._next("grant"),
            scope=self.scope,
            max_run_duration=self.max_run_duration,
            expires_at=self._now() + self.ttl_seconds,
        )
        self._grants[grant.grant_id] = grant
        # the descriptor nonce is consumed
        del self._descriptors[nonce]
        return grant

    def redeem(self, grant_id: str) -> Dict:
        """Redeem a grant to release the pre-funded capped capability. Rejected on
        second use or after expiry. Returns the capability, never a reusable secret."""
        grant = self._grants.get(grant_id)
        if grant is None:
            raise PermissionError("unknown grant")
        if grant.used:
            raise PermissionError("grant already used (single-use)")
        if self._now() > grant.expires_at:
            raise PermissionError("grant expired")
        grant.used = True
        return {
            "ok": True, "capability": grant.capability, "scope": grant.scope,
            "max_run_duration": grant.max_run_duration, "settle_mode": grant.settle_mode,
        }


# --------------------------------------------------------------------------- #
# HTTP wrapper — faithful 402 over localhost.
# --------------------------------------------------------------------------- #
class _Handler(BaseHTTPRequestHandler):
    rail: X402Rail = None  # set on the server

    def log_message(self, *a):  # silence
        pass

    def _json(self, code: int, body: Dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/resource"):
            # no payment presented -> 402 with descriptor
            self._json(402, self.server.rail.payment_required())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        if self.path.startswith("/pay"):
            try:
                grant = self.server.rail.settle(body)
                self._json(200, grant.to_dict())
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif self.path.startswith("/redeem"):
            try:
                self._json(200, self.server.rail.redeem(body.get("grant_id", "")))
            except Exception as e:
                self._json(403, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})


@dataclass
class RailServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    rail: X402Rail

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://127.0.0.1:{port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def serve(rail: Optional[X402Rail] = None) -> RailServer:
    rail = rail or X402Rail()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.rail = rail
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return RailServer(httpd=httpd, thread=t, rail=rail)


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="x402 reference rail")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if not args.selftest:
        ap.print_help()
        return 0

    rail = X402Rail()
    print("== x402 reference rail self-test (TEST MODE — no real funds) ==")
    desc = rail.payment_required()
    nonce = desc["accepts"][0]["nonce"]
    print(f"1) GET /resource  -> HTTP 402 Payment Required")
    print(f"   descriptor: price={desc['accepts'][0]['price']} scope={desc['accepts'][0]['scope']} nonce={nonce[:18]}…")
    grant = rail.settle({"nonce": nonce, "mode": "test", "payer": "pre-authorized-budget"})
    print(f"2) POST /pay (mandate) -> TEST-MODE settle -> grant {grant.grant_id[:18]}… "
          f"(scope={grant.scope}, cap={grant.max_run_duration}m, single_use={grant.single_use})")
    cap = rail.redeem(grant.grant_id)
    print(f"3) POST /redeem -> capability released: {cap['capability']} (settle_mode={cap['settle_mode']})")
    try:
        rail.redeem(grant.grant_id)
    except PermissionError as e:
        print(f"4) second redeem correctly REJECTED: {e}")
    print("transcript complete: 402 -> mandate -> test-mode settle -> scoped single-use grant")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
