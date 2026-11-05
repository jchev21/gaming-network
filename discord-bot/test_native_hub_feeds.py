import unittest

from native_hub_feeds import public_lobby_lines, safe_text


class NativeChannelHubFeedsTests(unittest.TestCase):
    def sample(self):
        return {"source": "live", "games": [{
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "Community game",
            "game": "trivia",
            "status": "open",
            "mode": "first",
            "seats": 8,
            "confirmedCount": 3,
            "privateJoinInstructions": "SECRET-NEVER-DISPLAY",
            "players": [{"name": "private player"}],
            "hostToken": "SECRET-TOKEN",
        }]}

    def test_only_public_allowlisted_fields_render(self):
        text = public_lobby_lines(self.sample())
        self.assertIn("Community game", text)
        self.assertIn("3/8 seats", text)
        self.assertIn("123e4567-e89b-12d3-a456-426614174000", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("private player", text)

    def test_malformed_source_fails_closed(self):
        self.assertIn("unavailable", public_lobby_lines({"source": "sample", "games": []}))
        self.assertIn("unavailable", public_lobby_lines({}))
        self.assertIn("unavailable", public_lobby_lines(None))

    def test_empty_real_feed_is_honest(self):
        self.assertIn("No public game lobbies", public_lobby_lines({"source": "live", "games": []}))

    def test_invalid_id_and_capacity_rejected(self):
        raw = self.sample()
        raw["games"][0]["id"] = "https://attacker.example/private"
        self.assertIn("No public game lobbies", public_lobby_lines(raw))
        raw["games"][0]["id"] = "123e4567-e89b-12d3-a456-426614174000"
        raw["games"][0]["confirmedCount"] = 99
        self.assertIn("No public game lobbies", public_lobby_lines(raw))

    def test_no_markup_or_untrusted_mentions(self):
        raw = self.sample()
        raw["games"][0]["title"] = "@everyone **You won** <script>"
        text = public_lobby_lines(raw)
        self.assertNotIn("@everyone", text)
        self.assertNotIn("**You won**", text)
        self.assertNotIn("<script>", text)
        self.assertIn("You won", text)

    def test_limits_rendered_games_and_length(self):
        raw = self.sample()
        raw["games"] = [dict(raw["games"][0], title="X" * 400)] * 200
        text = public_lobby_lines(raw)
        self.assertEqual(text.count("seats"), 5)
        self.assertNotIn("X" * 100, text)

    def test_text_input_is_bounded(self):
        self.assertEqual(safe_text(None), "")
        self.assertEqual(safe_text("Safe **text**", 20), "Safe text")


if __name__ == "__main__":
    unittest.main()
