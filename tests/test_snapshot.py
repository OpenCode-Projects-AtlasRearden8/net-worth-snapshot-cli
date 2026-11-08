"""Tests for the net-worth-snapshot CLI, run with `python3 -m unittest
discover -s tests` or `python3 -m pytest tests` from the repo root."""

import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import snapshot as snap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ParseMoneyTests(unittest.TestCase):
    def test_plain_values(self):
        self.assertEqual(snap.parse_money("100"), Decimal("100"))
        self.assertEqual(snap.parse_money("2450.10"), Decimal("2450.10"))

    def test_commas_and_dollars(self):
        self.assertEqual(snap.parse_money("$11,150.00"), Decimal("11150.00"))
        self.assertEqual(snap.parse_money("1,234,567.89"), Decimal("1234567.89"))

    def test_parentheses_mean_negative(self):
        self.assertEqual(snap.parse_money("(480.22)"), Decimal("-480.22"))

    def test_trailing_minus(self):
        self.assertEqual(snap.parse_money("89.50-"), Decimal("-89.50"))

    def test_leading_minus(self):
        self.assertEqual(snap.parse_money("-579.57"), Decimal("-579.57"))

    def test_empty_and_garbage_raise(self):
        with self.assertRaises(ValueError):
            snap.parse_money("")
        with self.assertRaises(ValueError):
            snap.parse_money("abc")
        with self.assertRaises(ValueError):
            snap.parse_money(None)


class TypeTests(unittest.TestCase):
    def test_lia_words_flip_positive_balance(self):
        csv_path = tempfile.mktemp(suffix=".csv")
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent("""\
                account,type,balance
                Car loan,loan,8900.00
                Card,credit card,(480.22)
                Checking,asset,2450.10
                """))
        try:
            accounts = snap.read_accounts(csv_path)
        finally:
            os.unlink(csv_path)
        by_name = {a["name"]: a["balance"] for a in accounts}
        self.assertEqual(by_name["Car loan"], Decimal("-8900.00"))
        self.assertEqual(by_name["Card"], Decimal("-480.22"))
        self.assertEqual(by_name["Checking"], Decimal("2450.10"))


class TotalsTests(unittest.TestCase):
    def setUp(self):
        self.accounts = [
            {"name": "Checking", "balance": Decimal("2450.10")},
            {"name": "Savings", "balance": Decimal("12000.00")},
            {"name": "Car loan", "balance": Decimal("-8900.00")},
            {"name": "Card", "balance": Decimal("-480.22")},
        ]

    def test_totals(self):
        assets, debts, net = snap.totals(self.accounts)
        self.assertEqual(assets, Decimal("14450.10"))
        self.assertEqual(debts, Decimal("9380.22"))
        self.assertEqual(net, Decimal("5069.88"))

    def test_negative_net(self):
        accounts = [{"name": "Loan", "balance": Decimal("-1000")}]
        assets, debts, net = snap.totals(accounts)
        self.assertEqual((assets, debts, net),
                         (Decimal("0"), Decimal("1000"), Decimal("-1000")))


class MoneyTests(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(snap.money(Decimal("0")), "$0.00")
        self.assertEqual(snap.money(Decimal("-8900")), "-$8,900.00")
        self.assertEqual(snap.money(Decimal("1234567.89")), "$1,234,567.89")


class ReadAccountsTests(unittest.TestCase):
    def test_sample_data_file(self):
        path = os.path.join(ROOT, "sample_data", "accounts.csv")
        accounts = snap.read_accounts(path)
        self.assertEqual(len(accounts), 6)
        assets, debts, net = snap.totals(accounts)
        self.assertEqual(assets, Decimal("21250.65"))
        self.assertEqual(debts, Decimal("20530.22"))
        self.assertEqual(net, Decimal("720.43"))

    def test_missing_columns_raise(self):
        csv_path = tempfile.mktemp(suffix=".csv")
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("name,value\nFoo,100\n")
        try:
            with self.assertRaises(ValueError):
                snap.read_accounts(csv_path)
        finally:
            os.unlink(csv_path)

    def test_blank_and_comment_rows_skipped(self):
        csv_path = tempfile.mktemp(suffix=".csv")
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("account,balance\nCash,10\n\n# note,99\n")
        try:
            accounts = snap.read_accounts(csv_path)
        finally:
            os.unlink(csv_path)
        self.assertEqual([a["name"] for a in accounts], ["Cash"])


class HistoryTests(unittest.TestCase):
    def test_save_and_read_roundtrip(self):
        path = os.path.join(tempfile.mkdtemp(), "history.csv")
        snap.save_history(path, "2026-01", Decimal("100"), Decimal("40"), Decimal("60"))
        snap.save_history(path, "2026-03", Decimal("120"), Decimal("40"), Decimal("80"))
        rows = snap.read_history(path)
        self.assertEqual([r["month"] for r in rows], ["2026-01", "2026-03"])

    def test_upsert_replaces_same_month(self):
        path = os.path.join(tempfile.mkdtemp(), "history.csv")
        snap.save_history(path, "2026-01", Decimal("100"), Decimal("40"), Decimal("60"))
        snap.save_history(path, "2026-03", Decimal("120"), Decimal("40"), Decimal("80"))
        snap.save_history(path, "2026-01", Decimal("110"), Decimal("40"), Decimal("70"))
        rows = snap.read_history(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["net"], Decimal("70"))

    def test_read_missing_file_is_empty(self):
        self.assertEqual(snap.read_history("/nonexistent/history.csv"), [])


class MonthTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(snap.validate_month("2026-11"), "2026-11")

    def test_invalid(self):
        for bad in ("2026-13", "2026.10", "October 2026", "2026-1", "26-10"):
            with self.assertRaises(ValueError):
                snap.validate_month(bad)


class TrendTests(unittest.TestCase):
    CAREER = [
        {"month": "2026-01", "assets": Decimal(0), "debts": Decimal(0),
         "net": Decimal(-1000)},
        {"month": "2026-02", "assets": Decimal(0), "debts": Decimal(0),
         "net": Decimal(0)},
        {"month": "2026-03", "assets": Decimal(0), "debts": Decimal(0),
         "net": Decimal(1000)},
    ]

    def test_covers_negative_to_positive_range(self):
        text = "\n".join(snap.trend_block(self.CAREER))
        self.assertIn("-$1,000.00", text)
        self.assertIn("$1,000.00", text)

    def test_bars_ordered_by_month(self):
        text = "\n".join(snap.trend_block(self.CAREER))
        self.assertLess(text.index("2026-01"), text.index("2026-03"))

    def test_no_history_hint(self):
        lines = snap.trend_block([])
        text = "\n".join(lines)
        self.assertIn("no history yet", text)

    def test_sparkline(self):
        spark = snap.sparkline([Decimal(1), Decimal(2), Decimal(3)])
        self.assertEqual(len(spark), 3)
        self.assertLess(spark[0], spark[2])


class PageTests(unittest.TestCase):
    def test_one_page_contains_everything(self):
        path = os.path.join(ROOT, "sample_data", "accounts.csv")
        history = snap.read_history(os.path.join(ROOT, "sample_data", "history.csv"))
        text, assets, debts, net = snap.page(snap.read_accounts(path),
                                             "2026-10", history)
        self.assertIn("NET WORTH SNAPSHOT -- 2026-10", text)
        self.assertIn("Assets", text)
        self.assertIn("$20,530.22", text)
        self.assertIn("2026-04", text)
        self.assertIn("not advice", text)
        for line in text.splitlines():
            self.assertLessEqual(len(line), snap.PAGE_WIDTH + 2)


def run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "snapshot.py")] + args,
        cwd=cwd, capture_output=True, text=True, timeout=60)


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = temppath = tempfile.mkdtemp()
        self.workdir = tmp
        result = run_cli(["sample", "--out", "sample"], self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sample_end_to_end(self):
        result = run_cli(
            ["snapshot", "--accounts", os.path.join("sample", "accounts.csv"),
             "--history", os.path.join("sample", "history.csv"),
             "--month", "2026-11", "--save"],
            self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NET WORTH SNAPSHOT -- 2026-11", result.stdout)
        self.assertIn("Saved 2026-11", result.stdout)
        ledger = open(os.path.join(self.workdir, "sample", "history.csv"),
                      encoding="utf-8").read()
        self.assertIn("2026-11", ledger)

    def test_trend_subcommand(self):
        result = run_cli(["trend", "--history",
                          os.path.join("sample", "history.csv")],
                         self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2026-04", result.stdout)

    def test_sample_refuses_to_overwrite(self):
        result = run_cli(["sample", "--out", "sample"], self.workdir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Refusing", result.stdout)

    def test_bad_month_errors_cleanly(self):
        result = run_cli(
            ["snapshot", "--accounts", "sample/accounts.csv",
             "--month", "october"], self.workdir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)

    def test_missing_accounts_file(self):
        result = run_cli(["snapshot", "--accounts", "nope.csv"], self.workdir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)

    def test_help(self):
        result = run_cli(["--help"], self.workdir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Not advice", result.stdout)


if __name__ == "__main__":
    unittest.main()
