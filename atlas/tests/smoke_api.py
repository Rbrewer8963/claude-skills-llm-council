"""End-to-end API smoke test: boot the real server, hit it, assert, shut down.

Runnable standalone (used by CI) and importable by the unittest suite. Binds to
port 0 so the OS picks a free port — no fixed-port collisions in CI.
"""

import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas.config import Config
from atlas.samples import demo_history, demo_portfolio
from atlas.server import make_server


def _payload():
    pf = demo_portfolio()
    hist = demo_history()
    return {
        "name": pf.name,
        "positions": [
            {"symbol": p.asset.symbol, "asset_class": p.asset.asset_class,
             "sector": p.asset.sector, "quantity": p.quantity, "price": p.price}
            for p in pf.positions
        ],
        "prices": {s: hist.prices[s] for s in hist.symbols},
        "horizon_days": 3,
        "n_paths": 400,
    }


def _get(base, path):
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
        return r.status, json.loads(r.read())


def _post(base, path, body):
    req = urllib.request.Request(
        f"{base}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read())


def main() -> int:
    from dataclasses import replace
    httpd = make_server(replace(Config(), host="127.0.0.1", port=0))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        status, health = _get(base, "/health")
        assert status == 200 and health["status"] == "ok", health

        status, ver = _get(base, "/version")
        assert status == 200 and ver["name"] == "atlas", ver

        status, analysis = _post(base, "/analyze", _payload())
        assert status == 200, analysis
        assert analysis["risk"]["var_95_1d"] > 0, analysis
        assert len(analysis["stress"]) == 4, analysis

        status, opt = _post(base, "/optimize",
                            dict(_payload(), method="risk_parity"))
        assert status == 200, opt
        assert abs(sum(opt["weights"].values()) - 1.0) < 1e-6, opt

        # Bad input must be a clean 400, not a crash.
        try:
            _post(base, "/risk", {"positions": []})
            raise AssertionError("expected HTTP 400 for empty positions")
        except urllib.error.HTTPError as e:
            assert e.code == 400, e.code

        print("API smoke test passed on", base)
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
