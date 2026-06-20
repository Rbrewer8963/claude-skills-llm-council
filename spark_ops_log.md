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

## 2026-06-20 — `spark-24` full `.claude` backup  ⏳ (command generated, run on box)

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

## Outstanding (carried)

- [ ] **Rotate** leaked creds: Cloudflare Global API Key (→ scoped token), CF
      account password (+2FA), Duffel live token, cloudflared connector token.
- [ ] Move secret values out of auto-loaded `memory/reference_cloudflare.md`
      into `~/.secrets/*.env` (chmod 600, not git-tracked, not under `~/.claude`).
- [ ] Re-run redacted inventory on the **spark-24** account (transcript work was
      on `/home/spark-24`, inventory above was `/home/rbrewer1` — different boxes).
- [ ] Step 0c intraday Kronos edge test — run `intraday_backtest.py` on the box
      that actually hosts Kronos.
- [ ] Hold Cloudflare tooling setup until Global API Key is rotated.
