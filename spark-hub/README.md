# Spark Hub — central coordination point for the DGX boxes

This directory is the **single place** where Claude (web/Max-plan session) and the
DGX boxes (`spark-24`, `rbrewer1`) exchange everything *except secrets*. The boxes
push sanitized artifacts up; Claude reads/writes them from the web without the
metered CLI.

## Why this exists

- The DGX CLI was billing the API meter (the `ANTHROPIC_API_KEY` override). Doing
  the planning/config/review work from the web Max-plan session avoids that cost.
- Claude's web sandbox **cannot reach the DGX filesystem**. A git repo it *can*
  reach becomes the bridge: box → `git push` → hub → Claude operates → `git push`
  → box → `git pull`.

## The one hard rule: NO SECRETS IN THE HUB

Raw secret values never enter this repo. They caused the billing leak and a
plaintext Cloudflare Global API Key. The boundary:

| Lives in the hub (sanitized)        | Lives ONLY on the box (`~/.secrets/*.env`, chmod 600) |
|-------------------------------------|--------------------------------------------------------|
| Code, configs, `.env.example`       | Real API keys, tokens, passwords                       |
| Redacted inventories (key *names*)  | `.credentials.json`                                    |
| Backtest results (sanitized)        | cloudflared connector token                            |
| Ops logs, plans, docs               | Duffel live token, CF Global API Key                   |

`.gitignore` at repo root hard-blocks `*.env`, `*credentials*`, `*secret*`,
`*token*`, `*.gpg`, `*.tar.gz`, etc. If a commit ever tries to add a secret, the
ignore rules should stop it — but the box-side scripts also redact before push.

## Layout

```
spark-hub/
├── README.md                  ← this file
├── inventory/                 ← redacted machine inventories (one per box)
├── results/                   ← sanitized backtest / job outputs
├── configs/                   ← service configs + *.env.example templates
├── plans/                     ← project plans, decisions
└── scripts/
    ├── backup_and_inventory.sh  ← run ON each box: backup .claude + redacted inventory
    └── dgx_push.sh              ← run ON each box: sync sanitized artifacts → hub
```

(`results/` and `tmp/` are gitignored for transient runs; commit final results
explicitly with `git add -f spark-hub/results/<name>` once sanitized.)

## Workflow

1. On a box: `bash spark-hub/scripts/backup_and_inventory.sh` → encrypted backup
   stays local; redacted inventory lands in `spark-hub/inventory/`.
2. On a box: `bash spark-hub/scripts/dgx_push.sh` → commits + pushes sanitized
   artifacts to this branch.
3. Claude (web) pulls, reviews, writes configs/plans back, pushes.
4. On a box: `git pull` to receive Claude's work; run GPU/trading jobs locally.

## Status carried from session 2026-06-20

- [ ] Rotate leaked creds (CF Global API Key → scoped token, CF password +2FA,
      Duffel live token, cloudflared token) — **blocks Cloudflare tooling setup**
- [ ] Move secret values into `~/.secrets/*.env`; strip them from the auto-loaded
      `memory/reference_cloudflare.md`
- [ ] Re-run inventory on the **spark-24** account (prior one was `rbrewer1`)
- [ ] Confirm which box hosts Kronos, then run Step 0c (`intraday_backtest.py`)
- [ ] Re-auth DGX CLI to Max (`claude /logout && /login`) to stop API billing
