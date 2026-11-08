# net-worth-snapshot

A tiny **offline** Python CLI that turns a small CSV of account names and
balances into a clean **one-page monthly net worth snapshot**: your assets,
your debts, and a plain-text trend line of how your net worth has moved month
by month.

Runs anywhere Python 3.8+ runs. No network. No dependencies beyond the
standard library. No accounts created, no data sent anywhere — your numbers
stay in your files.

This tool does the *totals* side of your money. It is deliberately distinct
from sibling tools that handle other jobs: `debt-payoff-planner-cli`
(deciding how to attack debts) and `cashflow-simple-ledger` (tracking money
moving in and out over time). Here, we only ask one question once a month:
*where do I stand?*

## What it is not

**This is not financial advice.** The snapshot prints a "Frame" note on every
page: it is bookkeeping, a picture of the numbers you typed in, and figures
can be wrong, incomplete, or stale. For guidance about money, talk to a
qualified fee-only professional. The tool will never tell you what to buy,
sell, or owe toward.

## Quick start

```sh
# 1. Make sample files and peek at them
python3 snapshot.py sample

# 2. Render your snapshot (defaults: accounts.csv, history.csv, current month)
python3 snapshot.py snapshot --accounts sample_data/accounts.csv \
    --history sample_data/history.csv --month 2026-11

# 3. Start building a history -- adds this month to the ledger file
python3 snapshot.py snapshot --accounts sample_data/accounts.csv \
    --history sample_data/history.csv --month 2026-11 --save

# 4. Show just the trend later
python3 snapshot.py trend --history sample_data/history.csv
```

## Your accounts CSV

The accounts file needs an `account` column and a `balance` column; an
optional `type` column helps label loans. A balance sign is all the math:
positive is an asset, negative is a debt. If `type` says something like
`loan`, `debt`, `credit card`, or `mortgage` while the number is positive,
the tool assumes you meant it as a debt.

```csv
account,type,balance
Checking,asset,2450.10
Savings,asset,12000.00
Index fund,asset,6800.55
Car loan,loan,8900.00
Credit card,credit card,(480.22)
Student loan,debt,"$11,150.00"
```

`$`, commas, thousands separators, parentheses (old ledger style for
negatives) are all handled.

## The history ledger

`--save` upserts one row per month into a plain CSV ledger:

```csv
month,assets,debts,net_worth
2026-09,21501.30,20466.77,1034.53
2026-11,21250.65,20530.22,720.43
```

Re-running with the same month replaces that row, so erasing a typo is just
"save the month again." The trend line renders from this file with plain
ASCII ramp bars (`.:-=+*#%@`) that low-to-high scale automatically — negative
net worth renders just fine.

## Output sample

```
==============================================================
 NET WORTH SNAPSHOT -- 2026-11
==============================================================

Accounts (6)
  A Savings                          $12,000.00
  ...
  D Student loan                    -$11,150.00

Totals
  Assets         $21,250.65
  Debts          $20,530.22
  Net               $720.43

Trend (net worth by month)
  .:=*%@#   (each char = one month, lowest..highest)
  2026-06   |==================================| $79.87
  ...
  2026-11 * |##################################| $720.43

Frame
  This is bookkeeping, not advice ...
```

## Commands and options

| Command | Purpose |
| --- | --- |
| `snapshot` | read accounts, print the one-page snapshot |
| `trend` | print just the monthly trend block |
| `sample` | write step-by-step sample CSVs you can edit |

Shared options: `--accounts PATH`, `--history PATH`, `--month YYYY-MM`,
`--save` (snapshot subcommand), `--out DIR` / `--force` (sample subcommand).

## Tests

```sh
python3 -m unittest discover -s tests
```

The suite covers money parsing, sign/type handling, totals, month validation,
history upsert, negative-value trend scaling, page layout, and full
end-to-end CLI runs on the sample data.

## Privacy-first design

- Local-first: the only files it reads or writes are the ones you name.
- No network calls of any kind.
- No built-in account numbers, credentials, or personal data — and none
  should be added.

## Credits

Built by **Asdale Dynamics, LLC** — beginner-friendly AI books, guides, and
practical, local-first tools. Learn more at dylanasdale.github.io.

Licensed under the MIT License (`LICENSE`).
