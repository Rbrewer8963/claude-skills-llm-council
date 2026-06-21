# Spark / DGX Ops Log

Running record of operations across the DGX Spark boxes. Maintained from the
coordination session (separate sandbox — cannot reach the boxes directly).

---

## 2026-06-20 — `rbrewer1` full `.claude` backup  ✅

Backup of the entire `~/.claude` tree on the `rbrewer1` account.

| Field | Value |
|---|---|
| File | `/home/rbrewer1/Claude/Documents/claude_full_20260620_164659.tar.gz` |
| Size | 41 MB (tar+gzip of ~120 MB raw) |
| Sessions captured | 48 `.jsonl` transcripts |
| Memory files | 113 `.md` |
| Total entries | 1281 (CLAUDE.md, rules/, hooks/, agents/, skills/, plugins/, landing-template.html, settings, `.credentials.json`) |
| SHA256 | `58148f3e55f08cfbfb3675b5c4de33fe5c8e12d5f39bda5921ea2bb1af42f4b6` |
| Restic | will be picked up by `spark-backup.timer` tonight @ 03:30 |

**⚠️ Sensitive — tarball must be treated as a secret:**
- `.claude/.credentials.json` — Claude Code auth credentials
- `.claude/projects/-home-rbrewer1/memory/reference_cloudflare.md` — plaintext
  Cloudflare account password + Global API Key + Duffel live/test tokens (GAP #2)
- Action: encrypt before any transfer (`gpg -c` or `age -p`), delete plaintext.
- **Open risk:** these secrets are unrotated and live. Backup propagates the leak
  into restic until rotation is done. Re-back up after rotation.

---

## 2026-06-20 — `spark-24` backup + inventory  ✅ (done on box, NOT yet in hub)

Run by the spark-24 CLI via ad-hoc commands (did **not** use hub scripts, so
artifacts are local to spark-24 only — pending `dgx_push.sh` to reach the hub).

| Field | Value |
|---|---|
| Inventory | `/home/spark-24/Claude/Documents/spark24_inventory_REDACTED.md` (435 lines, 7 §, masked) |
| Backup | `/home/spark-24/Claude/Documents/claude_full_20260620_160232.tar.gz` |
| Size | 130 MB |
| Sessions | 4,298 `.jsonl` (vs 48 on spark-23/rbrewer1 — spark-24 is the heavy box) |
| Memory | 194 `.md` |
| Entries | 7,394 |
| SHA256 | `de5b3c6b744fca948d15ff7670c0d89ef99bce3f4486bd4f2e1ca45a73de787f` |

Box mapping clarified: **rbrewer1 = spark-23** (48 sessions); **spark-24** = heavy box.

### 🔴 spark-24 GAPS (15 total in §7; the acute ones):
1. **LIVE Polygon MEV private key in plaintext** — `~/.mev_wallet.env`
   (`MEV_PRIVKEY <set, len=64>`). `mev-searcher.service` actively trades this
   wallet. **Most acute risk on either box — anyone who reads the file drains it.**
2. Stripe secret key duplicated across **~17 `.env` files** (same Senior Solutions acct).
3. Three `ANTHROPIC_API_KEY` entries (`.hermes/.env` ×2, `okayspark/.env`) — the
   billing culprit; consolidate to one, prefer Max OAuth.
4. `zc-tunnel.service` quick-tunnel (`cloudflared --url http://localhost:80`) →
   random public `*.trycloudflare.com` exposing whatever is on :80. Confirm or kill.
5. 12 `zc_gate/instances/*.env` Stripe paywalls; `verify.env` has a malformed
   `STRIPE_SECRET_KEY` (len 18 — too short to be real).
6. Testnet privkeys in `~/.creatorpay_wallet.{base-sepolia,polygon-amoy}.env`
   (lower risk); mainnet one correctly `<empty>` (disabled).

Note: the `.tar.gz` backs up `~/.claude` only, so the MEV key (`~/.mev_wallet.env`,
outside `.claude`) is **not** inside it — but it is plaintext on disk regardless.

---

## (superseded) spark-24 backup command — was generated, box ran its own

Equivalent backup for the `spark-24` account. Encrypts by default since the tree
contains `.credentials.json` and likely the same plaintext-secret pattern.

```bash
# Run AS spark-24 on the DGX (ssh spark-24@100.99.159.104)
set -euo pipefail
mkdir -p ~/Claude/Documents
DEST=~/Claude/Documents/claude_full_$(date +%Y%m%d_%H%M%S).tar.gz

tar --warning=no-file-changed -czf "$DEST" -C ~ .claude

echo "--- backup written ---"
ls -lh "$DEST"
echo "SHA256:   $(sha256sum "$DEST" | awk '{print $1}')"
echo "sessions: $(tar tzf "$DEST" | grep -c '\.jsonl$' || true)"
echo "memory:   $(tar tzf "$DEST" | grep -c '/memory/.*\.md$' || true)"
echo "entries:  $(tar tzf "$DEST" | grep -vc '/$' || true)"

# Encrypt before restic touches it (tarball holds .credentials.json + secrets)
gpg -c "$DEST" && shred -u "$DEST"
echo "--- encrypted -> ${DEST}.gpg, plaintext shredded ---"
```

Log the resulting filename, size, SHA256, and counts back into this file once run.

**⚠️ Same sensitivity applies** — check spark-24's
`~/.claude/.../memory/` for any `reference_*.md` holding plaintext secrets and
fold them into the rotation list before this backup is trusted.

---

## Outstanding — reordered by blast radius (2026-06-20)

- [ ] **#1 MEV wallet (live funds).** Can't rotate a privkey in place: generate a
      NEW keypair, move funds out of the exposed wallet, point `mev-searcher.service`
      at the new key in `~/.secrets/`, destroy old key. `chmod 600 ~/.mev_wallet.env`
      immediately as a stopgap.
- [ ] **#2 Stripe secret key.** Roll in Stripe dashboard; consolidate the ~17 copies
      to ONE source in `~/.secrets/stripe.env`, referenced everywhere. Fix malformed
      `verify.env` key.
- [ ] **#3 Cloudflare Global API Key** → scoped token; CF password +2FA; Duffel live
      token; cloudflared connector token. (spark-23 finding, still open.)
- [ ] **#4 Consolidate ANTHROPIC_API_KEY** to one + re-auth CLI to Max (stops API billing).
- [ ] **#5 zc-tunnel** quick-tunnel on :80 — confirm intended or `systemctl disable --now zc-tunnel`.
- [ ] Push spark-24 redacted inventory into the hub (`dgx_push.sh`) so it's usable here.
- [ ] Strip secret values from auto-loaded `memory/reference_*.md` → `~/.secrets/`.
- [ ] Step 0c intraday Kronos test on the box that hosts Kronos.
- [ ] Hold Cloudflare tooling setup until #3 is rotated.
