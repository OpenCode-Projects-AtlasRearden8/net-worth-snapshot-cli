#!/usr/bin/env python3
"""net-worth-snapshot -- a tiny offline CLI that turns a CSV of account
balances into a clean one-page monthly net worth snapshot.

Runs anywhere Python 3.8+ runs. No network. No dependencies. No advice.

Typical use:

    python3 snapshot.py snapshot --accounts accounts.csv --save
    python3 snapshot.py trend
    python3 snapshot.py sample
"""

import argparse
import csv
import os
import re
import sys
import textwrap
from datetime import date
from decimal import Decimal, InvalidOperation

RAMP = ".:-=+*#%@"
BAR_WIDTH = 34
PAGE_WIDTH = 62

DISCLAIMER = (
    "This is bookkeeping, not advice: a picture of what you typed in, "
    "nothing more. Figures may be wrong or stale. For guidance about "
    "money, see a qualified fee-only professional; this tool will never "
    "tell you what to buy, sell, or owe toward."
)


def parse_money(raw):
    if raw is None:
        raise ValueError("missing balance")
    text = str(raw).strip().replace("$", "").replace(",", "").replace("_", "")
    if not text:
        raise ValueError("empty balance")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.endswith("-"):
        negative = not negative
        text = text[:-1]
    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("not a number: %r" % raw)
    if negative:
        value = -value
    return value


LIA_WORDS = {"liability", "liabilities", "debt", "debts", "loan", "credit",
             "credit card", "mortgage", "owe", "owes"}


def normalize_type(raw):
    text = (raw or "").strip().lower()
    if text in ("asset", "assets", "bank", "cash", "investment", "savings", "a"):
        return "asset"
    if text in LIA_WORDS or text in ("l", "d"):
        return "debt"
    return ""


def read_accounts(path):
    accounts = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = [f.strip().lower() if f else "" for f in (reader.fieldnames or [])]
        if reader.fieldnames is None:
            raise ValueError("%s is empty" % path)
        name_col = next((f for f in reader.fieldnames if f and f.strip().lower() == "account"), None)
        bal_col = next((f for f in reader.fieldnames if f and f.strip().lower() in ("balance", "balances", "amount")), None)
        type_col = next((f for f in reader.fieldnames if f and f.strip().lower() in ("type", "kind", "category")), None)
        if name_col is None or bal_col is None:
            raise ValueError(
                "%s must have 'account' and 'balance' columns (found: %s)"
                % (path, ", ".join(reader.fieldnames))
            )
        for row in reader:
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            if name.lower().startswith("#"):
                continue
            balance = parse_money(row.get(bal_col))
            kind = normalize_type(row.get(type_col) if type_col else "")
            if kind == "debt" and balance > 0:
                balance = -balance
            accounts.append({"name": name, "balance": balance})
    if not accounts:
        raise ValueError("%s contains no account rows" % path)
    return accounts


def totals(accounts):
    assets = Decimal(0)
    debts = Decimal(0)
    for item in accounts:
        if item["balance"] >= 0:
            assets += item["balance"]
        else:
            debts += -item["balance"]
    return assets, debts, assets - debts


def money(value):
    value = Decimal(value)
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    text = "{:,.2f}".format(magnitude)
    return "%s$%s" % (sign, text)


def _right(text, width):
    return text[-width:].rjust(width)


def _left(text, width):
    return text[:width].ljust(width)


def history_sort_key(month):
    return month


def read_history(path):
    """Return a list of {month, assets, debts, net} dicts, oldest first."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            month = (row.get("month") or "").strip()
            if not month:
                continue
            rows.append({
                "month": month,
                "assets": parse_money(row.get("assets", 0)),
                "debts": parse_money(row.get("debts", 0)),
                "net": parse_money(row.get("net_worth", 0)),
            })
    rows.sort(key=lambda r: r["month"])
    return rows


def save_history(path, month, assets, debts, net):
    rows = [r for r in read_history(path) if r["month"] != month]
    rows.append({"month": month, "assets": assets, "debts": debts, "net": net})
    rows.sort(key=lambda r: r["month"])
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["month", "assets", "debts", "net_worth"])
        for r in rows:
            writer.writerow([r["month"], "{:.2f}".format(r["assets"]),
                             "{:.2f}".format(r["debts"]),
                             "{:.2f}".format(r["net"])])
    os.replace(tmp, path)


def validate_month(month):
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("month must look like YYYY-MM, got %r" % month)
    year, mon = int(month[:4]), int(month[5:])
    if not 1 <= mon <= 12:
        raise ValueError("month number must be 01-12, got %02d" % mon)
    return month


def sparkline(values):
    if not values:
        return ""
    lo = min(values)
    hi = max(values)
    if hi == lo:
        mid = RAMP[len(RAMP) // 2]
        return mid * len(values)
    out = []
    for v in values:
        idx = int((v - lo) * (len(RAMP) - 1) / (hi - lo))
        out.append(RAMP[idx])
    return "".join(out)


def bar(value, lo, hi, width=BAR_WIDTH):
    if hi == lo:
        idx = len(RAMP) - 1
    else:
        idx = int((value - lo) * (len(RAMP) - 1) / (hi - lo))
    return RAMP[idx] * width


def trend_block(history, current_month=None, net=None):
    lines = []
    series = history
    if current_month and net is not None and not any(r["month"] == current_month for r in series):
        series = series + [{"month": current_month, "assets": Decimal(0),
                            "debts": Decimal(0), "net": net}]
    lines.append("Trend (net worth by month)")
    if not series:
        lines.append("(no history yet; use --save to start one)")
        return lines
    values = [r["net"] for r in series]
    lo = min(values)
    hi = max(values)
    if hi == lo:
        hi, lo = lo + 1, lo - 1
    lines.append("  " + sparkline(values) + "   (each char = one month, lowest..highest)")
    for r in series:
        marker = " *" if current_month and r["month"] == current_month else "  "
        lines.append("  %s%s |%s| %s" % (r["month"], marker,
                                         bar(r["net"], lo, hi), money(r["net"])))
    return lines


def page(accounts, month, history=(), disclaim=True):
    assets, debts, net = totals(accounts)
    lines = []
    rule = "=" * PAGE_WIDTH
    lines.append(rule)
    lines.append(" NET WORTH SNAPSHOT -- %s" % month)
    lines.append(rule)
    lines.append("")
    lines.append("Accounts (%d)" % len(accounts))
    for item in sorted(accounts, key=lambda x: -x["balance"]):
        kind = "A" if item["balance"] >= 0 else "D"
        name = _left(item["name"], 27)
        lines.append("  %s %s %s" % (kind, name, _right(money(item["balance"]), 15)))
    lines.append("")
    lines.append("Totals")
    lines.append("  Assets %s" % _right(money(assets), 18))
    lines.append("  Debts  %s" % _right(money(debts), 18))
    lines.append("  Net    %s" % _right(money(net), 18))
    lines.append("")
    lines.append("")
    lines.extend(trend_block(history, month, net))
    lines.append("")
    months = len(history)
    lines.append("History: %d month%s on record in the ledger file."
                 % (months, "" if months == 1 else "s"))
    if disclaim:
        lines.append("")
        lines.append("Frame")
        for para in textwrap.wrap(DISCLAIMER, PAGE_WIDTH - 2):
            lines.append("  %s" % para)
    lines.append(rule)
    return "\n".join(lines), assets, debts, net


def current_month():
    return date.today().strftime("%Y-%m")


def cmd_snapshot(args):
    validate_month(args.month)
    accounts = read_accounts(args.accounts)
    history = read_history(args.history)
    text, assets, debts, net = page(accounts, args.month, history)
    print(text)
    if args.save:
        save_history(args.history, args.month, assets, debts, net)
        print("Saved %s to %s" % (args.month, args.history))
    return 0


def cmd_trend(args):
    history = read_history(args.history)
    lines = trend_block(history)
    print("\n".join(lines))
    if not history:
        return 1
    return 0


def cmd_sample(args):
    accounts_path = os.path.join(args.out, "accounts.csv")
    history_path = os.path.join(args.out, "history.csv")
    collision = [p for p in (accounts_path, history_path) if os.path.exists(p)]
    if collision and not args.force:
        print("Refusing to overwrite existing files (use --force): %s"
              % ", ".join(collision))
        return 1
    os.makedirs(args.out, exist_ok=True)
    with open(accounts_path, "w", newline="", encoding="utf-8") as fh:
        fh.write("account,type,balance\n")
        fh.write("Checking,asset,2450.10\n")
        fh.write("Savings,asset,12000.00\n")
        fh.write("Index fund,asset,6800.55\n")
        fh.write("Car loan,loan,8900.00\n")
        fh.write("Credit card,credit card,(480.22)\n")
        fh.write("Student loan,debt,\"$11,150.00\"\n")
    rows = [
        ("2026-04", "20850.65", "21430.22", "-579.57"),
        ("2026-05", "20950.15", "21305.00", "-354.85"),
        ("2026-06", "21060.20", "20980.33", "79.87"),
        ("2026-07", "21240.90", "20742.10", "498.80"),
        ("2026-08", "21385.44", "20510.55", "874.89"),
        ("2026-09", "21501.30", "20466.77", "1034.53"),
    ]
    with open(history_path, "w", newline="", encoding="utf-8") as fh:
        fh.write("month,assets,debts,net_worth\n")
        for row in rows:
            fh.write(",".join(row) + "\n")
    print("Wrote sample files:\n  %s\n  %s\n\nTry:\n  python3 snapshot.py snapshot --accounts %s --history %s --month 2026-10 --save"
          % (accounts_path, history_path, accounts_path, history_path))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="snapshot",
        description="Turn a tiny CSV of account balances into a one-page "
                    "monthly net worth snapshot, offline. Not advice.")
    parser.add_argument("--version", action="version",
                        version="net-worth-snapshot 1.0.0")
    sub = parser.add_subparsers(dest="command")

    p_snap = sub.add_parser("snapshot", help="read accounts and print one page")
    p_snap.add_argument("--accounts", default="accounts.csv",
                        help="CSV with 'account' and 'balance' columns")
    p_snap.add_argument("--history", default="history.csv",
                        help="ledger of monthly snapshots")
    p_snap.add_argument("--month", default=current_month(),
                        help="month label YYYY-MM (default: current month)")
    p_snap.add_argument("--save", action="store_true",
                        help="upsert this month's totals into the history file")
    p_snap.set_defaults(func=cmd_snapshot)

    p_trend = sub.add_parser("trend", help="print just the monthly trend line")
    p_trend.add_argument("--history", default="history.csv")
    p_trend.set_defaults(func=cmd_trend)

    p_sample = sub.add_parser("sample", help="write sample CSV files to try it")
    p_sample.add_argument("--out", default="sample_data",
                          help="directory for sample files (default: sample_data)")
    p_sample.add_argument("--force", action="store_true",
                          help="overwrite existing sample files")
    p_sample.set_defaults(func=cmd_sample)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (ValueError, InvalidOperation, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
