from __future__ import annotations

import unittest

from options_trader.retry import retry_call


class RetryTests(unittest.TestCase):
    def test_retry_call_retries_then_succeeds(self) -> None:
        calls = {"count": 0}

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 2:
                raise ValueError("temporary")
            return "ok"

        self.assertEqual(
            retry_call(flaky, attempts=2, base_delay_seconds=0, operation_name="test"),
            "ok",
        )
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()

