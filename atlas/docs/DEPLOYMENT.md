# ATLAS — Deployment Guide

ATLAS ships as an installable Python package with a zero-dependency JSON API and
a container image. This guide covers running it as a service — and, just as
importantly, an honest checklist of what "production for real capital" still
requires beyond the code in this repo.

---

## 1. Install

```bash
cd atlas
pip install .            # or: pip install -e .   for development
atlas --help
```

Because the engine has **no third-party runtime dependencies**, installation is
fast and the supply-chain surface is limited to the standard library.

## 2. Run the API

```bash
atlas serve                       # binds 0.0.0.0:8080 by default
ATLAS_PORT=9000 atlas serve       # override via env
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health`   | Liveness probe (returns `{"status":"ok"}`) |
| `GET`  | `/version`  | Service name + version |
| `POST` | `/analyze`  | Full report: risk + Monte-Carlo + stress + compliance |
| `POST` | `/risk`     | Risk analytics only |
| `POST` | `/stress`   | Stress-test suite |
| `POST` | `/optimize` | Construction: `min_variance` \| `max_sharpe` \| `risk_parity` |

Request bodies use the same JSON shape as the CLI's portfolio file (positions +
aligned `prices`). Example:

```bash
curl -s -X POST http://127.0.0.1:8080/risk \
  -H 'Content-Type: application/json' \
  -d @examples/sample_portfolio.json
```

## 3. Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `ATLAS_HOST` | `0.0.0.0` | Bind host |
| `ATLAS_PORT` | `8080` | Bind port |
| `ATLAS_LOG_LEVEL` | `INFO` | Application log level |
| `ATLAS_LOG_FORMAT` | `json` | `json` or `text` |
| `ATLAS_MAX_PATHS` | `200000` | Monte-Carlo path ceiling per request |
| `ATLAS_MAX_HORIZON_DAYS` | `3650` | Simulation horizon ceiling |
| `ATLAS_MAX_POSITIONS` | `5000` | Portfolio-size ceiling |
| `ATLAS_MAX_HISTORY_POINTS` | `20000` | Price-series length ceiling |
| `ATLAS_MAX_BODY_BYTES` | `25000000` | Request-body size limit |

These are guardrails so a single request cannot exhaust the host.

## 4. Container

```bash
docker build -t atlas-risk .
docker run --rm -p 8080:8080 atlas-risk
curl localhost:8080/health
```

The image runs as a non-root user, sets a `HEALTHCHECK`, and contains only the
standard library plus the package.

## 5. Operational behaviour

- **Structured logs** on stdout (JSON by default) for both the application and a
  separate **audit** logger that records every request served. Ship stdout to
  your log platform; the app is intentionally *not* the system of record.
- **Clean error contract:** malformed input returns `400` with a machine-readable
  `{"error", "detail"}` body; oversized bodies return `413`; unknown routes
  `404`. A stack trace is never leaked — the last-resort guard returns `500`
  with a generic message and logs the exception internally.
- **Stateless & horizontally scalable:** no shared state between requests, so
  run N replicas behind a load balancer. The threading server handles
  concurrent requests; for high throughput, front it with a reverse proxy.

## 6. CI

`.github/workflows/atlas-ci.yml` runs the unit suite, a CLI smoke test, and a
live-server API smoke test across Python 3.9 / 3.11 / 3.12 on every push and PR.

---

## 7. What "full production for real capital" still requires

The code here is a correct, tested, deployable **software artifact**. Running
real institutional money on *any* risk system additionally requires the
following — none of which is a code change, and all of which are deliberately
out of scope for this repository:

| Area | Requirement |
|---|---|
| **Market data** | Licensed, validated price/reference/corporate-action feeds and a data-quality pipeline. ATLAS ingests your data via CSV/JSON or the `dataio` seam; it does not source it. |
| **Model validation** | Independent quant review and back-testing (VaR exceedance/Kupiec tests) signing off the methodology before it drives decisions. |
| **Model realism** | Fat-tailed / historical-bootstrap shocks, covariance shrinkage, and constrained optimisation for production risk numbers (see `ARCHITECTURE.md` — each is a bounded extension point). |
| **Security** | AuthN/AuthZ on the API, TLS termination, secrets management, dependency and image scanning, pen testing. |
| **Compliance / audit** | Immutable, regulator-grade audit storage; change control; SOC 2 / regulatory sign-off. |
| **Resilience** | Persistence, backups, DR, SLOs, alerting, and load testing at expected scale. |
| **Performance** | For very large books / high path counts, a vectorised (NumPy) or compiled numerical core. |

Treat ATLAS as a verified reference engine you can deploy as a service today, and
as the analytical core to build a regulated platform around — not as a
turnkey replacement for a licensed, validated production risk system.
