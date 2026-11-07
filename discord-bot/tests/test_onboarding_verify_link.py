"""Verify the published #verify-x button actually enters the secure OAuth sequence."""
from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from community_onboarding import X_OAUTH_ENTRY, validate_oauth_entry


class OnboardingVerifyLinkTests(unittest.TestCase):
    def test_correct_same_origin_x_then_discord_oauth(self):
        self.assertTrue(validate_oauth_entry())
        url = urlparse(X_OAUTH_ENTRY)
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.hostname, "x-game-intake-production.up.railway.app")
        self.assertEqual(url.path, "/auth/x/start")
        self.assertEqual(parse_qs(url.query), {"next": ["/auth/discord/start"]})

    def test_not_my_games_or_external_return(self):
        self.assertFalse(validate_oauth_entry(
            "https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games"))
        self.assertFalse(validate_oauth_entry(
            "https://evil.example/auth/x/start?next=%2Fauth%2Fdiscord%2Fstart"))
        self.assertFalse(validate_oauth_entry(
            "https://x-game-intake-production.up.railway.app/auth/x/start?next=https%3A%2F%2Fevil.example"))
        self.assertFalse(validate_oauth_entry(
            "https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fauth%2Fdiscord%2Fstart-evil"))


if __name__ == "__main__":
    unittest.main()
