"""Owner authority regression: allowlist AND Discord guild permissions required."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from change_commands import _is_owner


def interaction(uid, *, owner_id=900, manage_guild=False, in_guild=True):
    user = SimpleNamespace(
        id=uid, guild_permissions=SimpleNamespace(manage_guild=manage_guild)
    )
    guild = SimpleNamespace(id=1566290427366080612, owner_id=owner_id) if in_guild else None
    return SimpleNamespace(user=user, guild=guild)


class OwnerPermissionsTests(unittest.TestCase):
    def test_explicit_owner_id_with_guild_ownership(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "42"}):
            self.assertTrue(_is_owner(interaction(42, owner_id=42)))

    def test_allowlisted_manage_server_operator(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "42"}):
            self.assertTrue(_is_owner(interaction(42, manage_guild=True)))

    def test_allowlisted_member_without_manage_server_denied(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "42"}):
            self.assertFalse(_is_owner(interaction(42)))

    def test_admin_not_on_allowlist_denied(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "42"}):
            self.assertFalse(_is_owner(interaction(44, manage_guild=True)))

    def test_direct_message_denied(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "42"}):
            self.assertFalse(_is_owner(interaction(42, in_guild=False)))

    def test_empty_allowlist_denies_server_owner(self):
        with patch.dict(os.environ, {"CHANGE_BRIDGE_OWNER_IDS": "", "DISCORD_OWNER_IDS": ""}):
            self.assertFalse(_is_owner(interaction(42, owner_id=42)))


if __name__ == "__main__":
    unittest.main()
