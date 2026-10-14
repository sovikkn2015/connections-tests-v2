"""
Unit tests for resolve_symbol() and _is_yahoo_only() in market-data/app.py.

Offline tests — no network. Run:
    FINNHUB_API_KEY=fake_for_test python3 test_resolve_symbol.py
"""

import os
import sys
import unittest

os.environ.setdefault("FINNHUB_API_KEY", "fake_for_test")

sys.path.insert(0, os.path.dirname(__file__))
from app import resolve_symbol, _is_yahoo_only  # noqa: E402


class TestResolveSymbol(unittest.TestCase):
    def test_equity_tickers_pass_through(self):
        for raw in ("AAPL", "aapl", "NVDA", "msft"):
            self.assertEqual(resolve_symbol(raw), raw.upper())

    def test_sp500_aliases(self):
        for raw in ("S&P 500", "s&p500", "sp500", "SP 500", "SPX"):
            self.assertEqual(resolve_symbol(raw), "^GSPC")

    def test_nasdaq_aliases(self):
        self.assertEqual(resolve_symbol("nasdaq"), "^IXIC")
        self.assertEqual(resolve_symbol("nasdaq composite"), "^IXIC")
        self.assertEqual(resolve_symbol("nasdaq 100"), "^NDX")

    def test_dow_and_vix(self):
        self.assertEqual(resolve_symbol("dow"), "^DJI")
        self.assertEqual(resolve_symbol("DJIA"), "^DJI")
        self.assertEqual(resolve_symbol("vix"), "^VIX")

    def test_treasuries(self):
        for raw in ("10y", "10-year", "10-year treasury", "10 year treasury"):
            self.assertEqual(resolve_symbol(raw), "^TNX")
        self.assertEqual(resolve_symbol("30y"), "^TYX")
        self.assertEqual(resolve_symbol("2y"), "^IRX")

    def test_crude_oil(self):
        for raw in ("crude", "WTI", "crude oil", "oil", "wti crude"):
            self.assertEqual(resolve_symbol(raw), "CL=F")

    def test_commodities(self):
        self.assertEqual(resolve_symbol("gold"), "GC=F")
        self.assertEqual(resolve_symbol("silver"), "SI=F")
        self.assertEqual(resolve_symbol("natural gas"), "NG=F")
        self.assertEqual(resolve_symbol("brent"), "BZ=F")

    def test_crypto(self):
        self.assertEqual(resolve_symbol("btc"), "BTC-USD")
        self.assertEqual(resolve_symbol("bitcoin"), "BTC-USD")
        self.assertEqual(resolve_symbol("eth"), "ETH-USD")

    def test_fx(self):
        self.assertEqual(resolve_symbol("eurusd"), "EURUSD=X")
        self.assertEqual(resolve_symbol("usd/jpy"), "JPY=X")
        self.assertEqual(resolve_symbol("dxy"), "DX-Y.NYB")

    def test_yahoo_verbatim(self):
        self.assertEqual(resolve_symbol("^GSPC"), "^GSPC")
        self.assertEqual(resolve_symbol("CL=F"), "CL=F")
        self.assertEqual(resolve_symbol("BTC-USD"), "BTC-USD")

    def test_empty_input(self):
        self.assertEqual(resolve_symbol(""), "")
        self.assertEqual(resolve_symbol(None), None)


class TestIsYahooOnly(unittest.TestCase):
    def test_indices(self):
        self.assertTrue(_is_yahoo_only("^GSPC"))
        self.assertTrue(_is_yahoo_only("^TNX"))
        self.assertTrue(_is_yahoo_only("^VIX"))

    def test_futures(self):
        self.assertTrue(_is_yahoo_only("CL=F"))
        self.assertTrue(_is_yahoo_only("GC=F"))

    def test_crypto(self):
        self.assertTrue(_is_yahoo_only("BTC-USD"))
        self.assertTrue(_is_yahoo_only("ETH-USD"))

    def test_fx(self):
        self.assertTrue(_is_yahoo_only("EURUSD=X"))

    def test_equities_are_not_yahoo_only(self):
        self.assertFalse(_is_yahoo_only("AAPL"))
        self.assertFalse(_is_yahoo_only("NVDA"))
        self.assertFalse(_is_yahoo_only("TSLA"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
