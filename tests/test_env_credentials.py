from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from options_trader.alpaca.client import AlpacaSettings
from options_trader.config.env import dotenv_values, environment_with_dotenv, load_dotenv


class EnvCredentialsTests(unittest.TestCase):
    def test_dotenv_values_parse_common_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "export ALPACA_PAPER_API_KEY_ID=paper-key",
                        'ALPACA_PAPER_SECRET_KEY="paper secret"',
                        "ALPACA_LIVE_SECRET_KEY=live-secret # inline comment",
                    ]
                ),
                encoding="utf-8",
            )

            values = dotenv_values(env_path)

        self.assertEqual(values["ALPACA_PAPER_API_KEY_ID"], "paper-key")
        self.assertEqual(values["ALPACA_PAPER_SECRET_KEY"], "paper secret")
        self.assertEqual(values["ALPACA_LIVE_SECRET_KEY"], "live-secret")

    def test_load_dotenv_does_not_override_existing_shell_values(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ALPACA_PAPER_API_KEY_ID=from-file\n", encoding="utf-8")
            environ = {"ALPACA_PAPER_API_KEY_ID": "from-shell"}

            load_dotenv(env_path, environ=environ)

        self.assertEqual(environ["ALPACA_PAPER_API_KEY_ID"], "from-shell")

    def test_environment_with_dotenv_allows_explicit_env_override(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ALPACA_PAPER_API_KEY_ID=from-file\n", encoding="utf-8")

            environ = environment_with_dotenv(
                {"ALPACA_PAPER_API_KEY_ID": "from-shell"},
                env_path,
            )

        self.assertEqual(environ["ALPACA_PAPER_API_KEY_ID"], "from-shell")

    def test_alpaca_settings_selects_paper_and_live_credentials(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "ALPACA_PAPER_API_KEY_ID=paper-key",
                        "ALPACA_PAPER_SECRET_KEY=paper-secret",
                        "ALPACA_LIVE_API_KEY_ID=live-key",
                        "ALPACA_LIVE_SECRET_KEY=live-secret",
                    ]
                ),
                encoding="utf-8",
            )

            paper = AlpacaSettings.from_env(paper=True, env={}, dotenv_path=env_path)
            live = AlpacaSettings.from_env(paper=False, env={}, dotenv_path=env_path)

        self.assertEqual(paper.api_key, "paper-key")
        self.assertEqual(paper.secret_key, "paper-secret")
        self.assertTrue(paper.paper)
        self.assertEqual(live.api_key, "live-key")
        self.assertEqual(live.secret_key, "live-secret")
        self.assertFalse(live.paper)


if __name__ == "__main__":
    unittest.main()
