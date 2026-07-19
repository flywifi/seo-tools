# Local Context and the Offline Compute Lane

Two promises this document explains and shows how to verify:

1. **Your personal files stay on your computer.** Everything specific to you (your channel stats, your
   voice, your negotiating playbook, your real contracts, your obligation deadlines, your credentials)
   lives in files that are never committed to git and never pushed. When the repo updates, those files
   are left exactly as they are.
2. **The boring math runs on your computer, not in the model.** Deterministic work (deadline date
   math, deadline scans, register building, file verification) runs as local Python so it costs no
   tokens. The model asks for the result and gets it back; it never does the arithmetic itself.

## What stays local (and is never pushed)

Real, personal data lives in gitignored `*.local.*` files. Only blank templates and schemas are
committed. The committed template shows the shape; your real file sits next to it with `.local` in the
name and never enters git.

| Committed template (safe, blank) | Your real file (local only, gitignored) |
|---|---|
| `pipeline/user-context/channel-context.json` | `channel-context.local.json` |
| `pipeline/user-context/voice-profile.json` | `voice-profile.local.json` |
| `pipeline/user-context/creator-profile.template.json` | `creator-profile.local.json` |
| `pipeline/user-context/content-calendar.json` | `content-calendar.local.json` |
| `pipeline/user-context/deal-playbook.template.json` | `deal-playbook.local.json` |
| `pipeline/user-context/obligation-register.template.json` | `obligation-register.local.json` |
| `pipeline/contracts/contract.template.json` | `pipeline/contracts/<id>.local.json` (raw contract text) |
| `pipeline/deals/deal-schema.json` | `pipeline/deals/<id>.local.json` |
| `pipeline/finance/rate-card.template.json` | `pipeline/finance/rate-card.local.json` (your real rates) |
| `pipeline/finance/invoice.template.json` | `pipeline/finance/INV-<deal>-<seq>.local.json` |
| `pipeline/finance/cost-estimate.template.json` | `pipeline/finance/<estimate>.local.json` |
| `pipeline/finance/cost-actuals.template.json` | `pipeline/finance/cost-actuals.local.json` |
| (none) | `api-credentials.local.json`, `google-credentials.local.json`, `microsoft-credentials.local.json` |
| (none) | `creator-os-config.local.json`, `creator-os-connectors.local.json` |

`git pull` and repo updates never touch these `.local` files (git leaves untracked files alone), so
updating Creator OS never overwrites or exposes your data.

### The guarantee is enforced, not just promised

- **Drift-guard invariant 19** (`tools/sync_check.py`) fails the build if git is ever found tracking a
  `*.local.*` file. A stray `git add -A` cannot slip your personal data into a commit.
- **`python3 tools/local_privacy.py`** prints, in plain English, which files live only on your machine
  and confirms none are tracked. Run it any time you want reassurance.

```bash
python3 tools/local_privacy.py       # human-readable report
python3 tools/sync_check.py          # invariant 19 (and the rest) must pass
```

If you ever see a warning that a personal file is tracked, stop tracking it with
`git rm --cached <path>` and commit that removal.

## The offline compute lane

Some work is pure arithmetic and logic: computing when to send an invoice, rolling a deadline off a
weekend or holiday, sorting deadlines by urgency, verifying a file has not changed. There is no reason
to spend model tokens on it. Creator OS runs that work locally in Python and hands the result back.

The first realized instance is contract obligations (P23 Phase 3):

- `obligation-extract` (the model) reads a signed contract and lists the duties as rows, quoting the
  contract.
- `tools/obligations.py` (local Python, no network, no tokens) takes those rows and computes each
  obligation's effective date, send-by date (with weekend and US federal holiday roll-back), and
  urgency band, then writes the register to your local machine.
- The `import_obligations` handoff hands the computed deadlines to your content calendar, production
  tasks, and invoicing, so nothing is a parallel calendar.

```bash
# read-only: what is due and when to act (no writes, always available)
python3 tools/obligations.py --scan rows.json --today 2026-07-02

# compute and store the dated register (write gated by the contract_obligations flag)
python3 tools/obligations.py --build rows.json --today 2026-07-02 --write

# verify a register copied between machines (sha256, like the P22 editing bucket)
python3 tools/obligations.py --manifest --write-manifest obligations-bucket.manifest.json
python3 tools/obligations.py --verify obligations-bucket.manifest.json

# prove the date math on this machine any time (offline, no writes)
python3 tools/obligations.py --selftest

# the full 38-check handoff simulation (offline; all writes go to a throwaway
# sandbox that is deleted at the end; your real local files are proven untouched)
python3 tools/handoff_sim.py
```

Relative deadlines ("net 30 from delivery") round-trip too: the model supplies the anchor date from
the deal record on the row (`anchor_date` + `offset_days`), and the offline tool derives the actual
date, rolls it off weekends and holidays, and records how it got there. The model never adds the
days.

### The reusable pattern

Any future deterministic task follows the same shape, so it also saves tokens and keeps data local:

1. The model produces or reads structured input.
2. A local Python tool does the deterministic work over gitignored `.local` artifacts.
3. A sha256 bucket manifest lets an offline copy be verified before the online side trusts it.
4. An MCP import adapter hands the result back to the model, which interprets it.

This mirrors the P22 video-editing handoff (`tools/sync_editing.py`, `import_edit_artifact`, the
dashboard `/api/import-report` adapter). The model orchestrates and explains; the computer computes.

The second realized instance is the finance bucket (P30): `tools/finance.py` does the money math
(accounts-receivable aging, invoice assembly with due dates from structured net terms,
late-penalty accrual, revenue-share payouts, cost rollups, proposal price floors) in exact
decimal over `pipeline/finance/*.local.json` records. Reads (`--ar-scan`) are always available;
writes gate on the `finance_management` and `invoice_generation` flags; the same sha256 manifest
discipline (`--manifest` / `--verify`) applies; and the `finance_scan` / `invoice_build` /
`cost_rollup` / `proposal_price` / `import_finance` MCP tools are the handoff. The model never
does the arithmetic, and nothing money-facing is sent without an explicit human yes
(`shared/finance-engine.md`).

The third realized instance is the CRM read lane (P32): `tools/accounts.py` reads
`pipeline/accounts/*.local.json` and `pipeline/deals/*.local.json` to resolve a fuzzy brand phrase
to one account (tiered exact/alias/substring/difflib/brand-category matching that never auto-picks
past a confident exact or alias match), read its contacts, and report a deal's lifecycle status
verbatim. It is READ-ONLY (no write modes at all), CREATOR_OS_ROOT-sandboxed, carries `computed_by`
and `gaps[]`, and degrades to an empty result plus a gap on a fresh clone. Contacts are PII, so the
`contact_lookup` and `deal_status` MCP tools (and the `--redacted` CLI flag) mask names to initials <!-- verify: tools/accounts.py::deal_status -->
and emails to a stub for anything quoted off this machine; the raw result is for the human operator
here.

```bash
# read-only: resolve a fuzzy brand phrase, read a contact, or check a deal's stage
python3 tools/accounts.py --resolve "that lightbulb company"
python3 tools/accounts.py --contacts "hearthline" --person "marcus" --redacted
python3 tools/accounts.py --deal-status "lumen"

# read-only: who owes what, aged and prioritized (no writes, always available)
python3 tools/finance.py --ar-scan --today 2026-07-03

# draft an invoice (write gated by finance_management + invoice_generation)
python3 tools/finance.py --build-invoice payload.json --write

# weekly cash-movement view (read-only; add --redacted for anything leaving the machine)
python3 tools/finance.py --cashflow --horizon-days 90

# match a bank export to open invoices (proposal-only; the CSV must be a .local. path or outside the repo)
python3 tools/finance.py --reconcile pipeline/finance/checking.local.csv
```

## The privacy boundary (P31)

Financial data and PII are kept out of git by layered, machine-enforced controls, not convention:

1. **Data at rest.** `.gitignore` ignores everything under `pipeline/finance/` by default (only
   `*.template.json` and `*-schema.json` are allowlisted back in), plus all CSV/XLSX/PDF exports
   under `pipeline/`, `.env*`, key material, and common bank-export filename patterns. Drift
   invariant 20 verifies that every git-tracked file under `pipeline/` is on an explicit
   allowlist and that no sensitive-format file is tracked anywhere in the repo: the shared
   `tools/secret_scan.py::FORBIDDEN_DATA_SUFFIXES` list covers spreadsheets (XLS/XLSM/XLSB/ODS/
   Numbers), delimited and columnar exports (CSV/TSV/Parquet), financial application files
   (OFX/QFX/QBW/QBB/QIF/TAX), credential and key stores (PEM/KEY/P12/KDBX/keychain/.p8), databases
   and backups (SQLite/MDB/BAK/SQL dumps), email and contacts (PST/MBOX/EML/VCF), archives,
   office binaries (DOCX/PDF), and GPS-bearing capture media; invariant 19 keeps `.local.` files
   untracked. Both fail closed in CI, and print a loud DID-NOT-RUN advisory in a non-git copy.
2. **Content scanning.** `tools/secret_scan.py` (stdlib, offline) scans EVERY tracked file that
   passes a binary sniff (no suffix gate, so a stray `secrets.conf` or extensionless credential
   file is covered) for key material — including current hyphenated `sk-` provider key formats
   and fine-grained GitHub tokens — credential values, session links, personal emails, and
   amount figures in pipeline files. Wired as drift invariant 21 and a CI step. Verified false
   positives go in `tools/secret-scan-allowlist.json` with a written reason.
3. **Commit hygiene.** `python3 tools/install_hooks.py` installs a pre-commit hook (scans staged
   content) and a commit-msg hook (rejects messages carrying session links, emails, or secret
   patterns). CI re-checks commit messages and author emails after the policy boundary SHA in
   the allowlist file.
4. **Redaction for anything leaving the machine.** `finance.redact()` bands amounts into ranges
   and reduces brand names to initials; the `--redacted` CLI flag and the `redacted` parameter
   on the finance MCP tools apply it. The dashboard stays raw because it is localhost-only.
5. **Structural refusals.** `finance.reconcile()` refuses any CSV inside the repo tree unless the <!-- verify: tools/finance.py::reconcile -->
   filename contains `.local.`; dunning drafts are written only to gitignored `.local.md` paths
   and are never sent by the system.

`python3 tools/local_privacy.py` reports the live state of the boundary on this machine.

## Note

Contract work is legal information, never legal advice. The obligation register organizes dates from a
signed contract; it does not rule on enforceability. Review anything with legal consequences with a
qualified professional. See `shared/contract-engine.md` and `protocols/safety.md`.
