import unittest
from community_onboarding import COMMUNITY_RULES, X_OAUTH_ENTRY, validate_oauth_entry, public_onboarding_instructions

class OnboardingRulesTests(unittest.TestCase):
    def test_rule_count_is_small_and_suitable_for_discord_native_rules(self):
        self.assertGreaterEqual(len(COMMUNITY_RULES), 5)
        self.assertLessEqual(len(COMMUNITY_RULES), 16)
        self.assertTrue(all(15 <= len(x) <= 220 for x in COMMUNITY_RULES))
        self.assertEqual(len(set(COMMUNITY_RULES)), len(COMMUNITY_RULES))

    def test_x_login_points_only_to_official_backend(self):
        self.assertTrue(validate_oauth_entry())
        self.assertFalse(validate_oauth_entry("https://evil.example/auth/x/start?next=%2Fmy-games"))
        self.assertFalse(validate_oauth_entry("http://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games"))
        self.assertFalse(validate_oauth_entry("https://x-game-intake-production.up.railway.app.attacker.io/auth/x/start?next=%2Fmy-games"))
        self.assertFalse(validate_oauth_entry("https://x-game-intake-production.up.railway.app/auth/x/start?next=https%3A%2F%2Fevil.example"))
        self.assertFalse(validate_oauth_entry("https://user:password@x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games"))

    def test_no_false_discord_linking_or_role_promise(self):
        body = public_onboarding_instructions()
        for exact in ("Rules Screening", "X sign-in and Discord account linking are separate steps", "does not give you any Discord role", "coming soon"):
            self.assertIn(exact, body)
        self.assertNotIn("automatically verified", body.lower())
        self.assertNotIn("successfully linked", body.lower())

if __name__ == "__main__":
    unittest.main()
