# STATUS.md — net-worth-snapshot

Built 2026-11-08 by Asdale Dynamics, LLC.

## What was built

`snapshot.py` — a single-file, dependency-free, offline Python 3.8+ CLI that
turns a tiny CSV of account names and balances into a one-page monthly net
worth snapshot:

- **Accounts section** — each account tagged A (asset) or D (debt),
  sorted, with a signature-clean right-aligned money column.
- **Totals** — assets, debts, and net, computed with `Decimal` (no float
  drift). Sign-based math: positive is an asset, negative a debt; an
  optional `type` column (`loan`, `debt`, `credit card`, ...) flips
  positive balances into debts gracefully.
- **Trend line** — plain-text, ASCII-only ramp bars (`.:-=+*#%@`) plus a
  one-line sparkline, scaled automatically low-to-high; handles negative
  net worth months. Rendered from a `month,assets,debts,net_worth`
  ledger CSV.
- **Frame** — an explicit "bookkeeping, not advice" disclaimer prints on
  every rendered page, restated in the README.
- **Robust money parsing** — `$`, thousands commas, parentheses-for-
  negative, trailing minus; blank and `#`-comment CSV rows ignored.
- **History upsert** — `--save` writes/updates one row per month atomically
  (temp file + `os.replace`).
- `sample` command generates ready-to-edit sample CSVs (refuses to
  overwrite without `--force`).

Deliberately distinct from `debt-payoff-planner-cli` (payoff strategy) and
`cashflow-simple-ledger` (money in/out over time): this tool only answers
"where do I stand right now?" — totals, not flows or plans.

## How to run

```sh
python3 snapshot.py sample                 # get sample CSVs (sample_data/)
python3 snapshot.py snapshot --accounts sample_data/accounts.csv \
    --history sample_data/history.csv --month 2026-11 --save
python3 snapshot.py trend --history sample_data/history.csv
python3 snapshot.py --help
```

No network access, no third-party packages, stdlib only. Works on any
Python 3.8+ (verified on Python 3.13.5, Linux).

## Verification results

- `python3 -m unittest discover -s tests` — **29/29 tests pass**, ~0.4s.
  Coverage includes: money parsing variants, type/sign flipping, totals,
  month validation, history round-trip and upsert, negative-to-positive
  trend scaling, page-width layout guard, missing-file/column errors, and
  end-to-end CLI runs (`sample` → `snapshot --save` → `trend`) via
  subprocess on generated data.
- Manual end-to-end check in a temp directory: sample generation, snapshot
  render, upsert to ledger, and standalone trend all behaved as expected.
- Error paths verified: missing accounts file, wrong CSV header, invalid
  month label — all exit 1 with a clean `error:` message on stderr.
- Dummy money/account values only throughout; no real or personal data.

## Known gaps

- No import from bank statements or OFX — the tool stays honest by only
  reading numbers you type or curate yourself.
- Trend bars scale per render; they compare relative months, not to a
  fixed axis, so two separate runs are not pixel-comparable.
- History file is plain CSV with no locking — one writer at a time is
  assumed (fine for a personal monthly ritual).
- No `pyproject.toml` packaging yet; it is a copy-and-run script by
  design. A proper entry point could be added if published.
- Sample months use fictional round numbers.
