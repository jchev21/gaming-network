"""Safe owner-controlled channel reorganization and Rules Accepted role tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from discord_bot_change_bridge.diff import (
    GuildInventory, CategorySnap, ChannelSnap, build_plan_diff,
)
from discord_bot_change_bridge.schema import parse_proposal, plan_hash
from discord_bot_change_bridge.layout_overhaul import (
    build_move_batch, build_stage_proposal,
)
from onboarding_roles import (
    RULES_ROLE_NAME, MEMBER_ROLE_NAME,
    member_passed_rules, give_rules_accepted_if_screened,
    on_screening_update, onboarding_audit, dangerous_member_role,
)

GUILD = 1566290427366080612


class FakeRole:
    def __init__(self, role_id, name, position=1):
        self.id = role_id
        self.name = name
        self.position = position
        self.permissions = SimpleNamespace(
            administrator=False, manage_guild=False, manage_roles=False,
            manage_channels=False, manage_webhooks=False, manage_messages=False,
            ban_members=False, kick_members=False, moderate_members=False,
        )


class FakeGuild:
    id = GUILD
    def __init__(self, screening=True, manage_roles=True):
        self.features = ["MEMBER_VERIFICATION_GATE_ENABLED"] if screening else []
        self.roles = [FakeRole(100, RULES_ROLE_NAME), FakeRole(101, MEMBER_ROLE_NAME)]
        self.me = SimpleNamespace(
            guild_permissions=SimpleNamespace(manage_roles=manage_roles),
            top_role=FakeRole(999, "Bot", position=20),
        )
        self.text_channels = []


class FakeMember:
    def __init__(self, guild, *, pending=False, bot=False):
        self.guild = guild
        self.pending = pending
        self.bot = bot
        self.roles = []
        self.assignments = []
    async def add_roles(self, role, reason=None):
        self.roles.append(role)
        self.assignments.append(role.name)


class RoleGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_rules_pending_blocks_role(self):
        person = FakeMember(FakeGuild(), pending=True)
        self.assertFalse(member_passed_rules(person))
        self.assertIn("incomplete", await give_rules_accepted_if_screened(person))
        self.assertEqual(person.assignments, [])

    async def test_no_screening_feature_blocks_role(self):
        person = FakeMember(FakeGuild(screening=False), pending=False)
        self.assertIn("incomplete", await give_rules_accepted_if_screened(person))
        self.assertEqual(person.assignments, [])

    async def test_unprivileged_member_cannot_bypass_manage_roles(self):
        person = FakeMember(FakeGuild(manage_roles=False))
        self.assertIn("Manage Roles", await give_rules_accepted_if_screened(person))
        self.assertEqual(person.assignments, [])

    async def test_screened_user_gets_only_rules_accepted(self):
        person = FakeMember(FakeGuild(), pending=False)
        result = await give_rules_accepted_if_screened(person)
        self.assertIn("granted", result)
        self.assertEqual(person.assignments, [RULES_ROLE_NAME])
        await give_rules_accepted_if_screened(person)
        self.assertEqual(person.assignments, [RULES_ROLE_NAME])
        state = onboarding_audit(person.guild)
        self.assertTrue(state["rules_assignable"])
        self.assertTrue(state["member_role_safe"])
        self.assertFalse(state["x_to_discord_member_grant_enabled"])

    async def test_native_pending_transition_only(self):
        guild = FakeGuild()
        after = FakeMember(guild)
        with patch.dict("os.environ", {"GN_RULES_AUTOGRANT": "true"}):
            self.assertIsNone(await on_screening_update(FakeMember(guild, pending=False), after))
            self.assertEqual(after.assignments, [])
            result = await on_screening_update(FakeMember(guild, pending=True), after)
            self.assertIn("granted", result)
            self.assertEqual(after.assignments, [RULES_ROLE_NAME])

    async def test_high_privilege_member_role_is_rejected(self):
        role = FakeRole(10, MEMBER_ROLE_NAME)
        role.permissions.manage_guild = True
        self.assertTrue(dangerous_member_role(role))


class PublicMoveTests(unittest.TestCase):
    def inventory(self):
        categories = [
            CategorySnap(1, "Gaming Network — Start Here"),
            CategorySnap(2, "COMMUNITY"),
            CategorySnap(3, "GAMES & X"),
            CategorySnap(4, "ALGO LAB"),
            CategorySnap(5, "ALL FIRMS"),
            CategorySnap(6, "FEEDBACK"),
            CategorySnap(7, "DISCORD STUDIO"),
            CategorySnap(8, "AFFILIATES & MANAGERS"),
            CategorySnap(9, "EDUCATION"),
            CategorySnap(10, "PERSONAL HUB"),
            CategorySnap(11, "Text Channels"),
            CategorySnap(12, "BOT COMMANDS"),
            CategorySnap(13, "Restricted", private=True),
        ]
        channels = [
            ChannelSnap(1567827003414159365, "dashboard", "text", category_id=10),
            ChannelSnap(1567328326169796608, "announcements", "text", category_id=10),
            ChannelSnap(1568331098239537274, "start-here", "text"),
            ChannelSnap(1568085615722111117, "rules", "text"),
            ChannelSnap(1567328378690740265, "suggestions", "text", category_id=12),
            ChannelSnap(1567328370562433074, "payout-reports", "text", category_id=9),
            ChannelSnap(1567328368645644501, "algo-lab", "text", category_id=9),
            ChannelSnap(1568331258705219705, "gaming-videos", "text"),
            ChannelSnap(1567328348747730965, "prop-firm-feed", "text", category_id=13),
        ]
        return GuildInventory(guild_id=GUILD, categories=categories, channels=channels)

    def test_planned_moves_use_existing_ids_and_preserve_role_permissions(self):
        inv = self.inventory()
        raw = build_move_batch(inv, now_unix=100)
        self.assertIsNotNone(raw)
        proposal = parse_proposal(raw)
        names = [line.summary for line in build_plan_diff(
            proposal, inv, plan_hash(proposal)).lines]
        self.assertTrue(any("dashboard" in name and "COMMUNITY" in name for name in names))
        self.assertTrue(any("announcements" in name for name in names))
        self.assertFalse(any("prop-firm-feed" in name for name in names))
        self.assertTrue(all(x.op == "move_channel" for x in proposal.operations))
        self.assertFalse(build_plan_diff(proposal, inv, plan_hash(proposal)).blocked)

    def test_private_parent_skipped_and_name_mismatch_blocks_moves(self):
        inv = self.inventory()
        inv.channels[0] = ChannelSnap(1567827003414159365, "renamed-sensitive", "text", category_id=10)
        raw = build_move_batch(inv, now_unix=100)
        self.assertTrue(all(op["channel_id"] != 1567827003414159365 for op in raw["operations"]))

    def test_stage_requires_existing_public_community_and_feature(self):
        inv = self.inventory()
        self.assertIsNone(build_stage_proposal(inv, now_unix=100, community_enabled=False))
        raw = build_stage_proposal(inv, now_unix=100, community_enabled=True)
        proposal = parse_proposal(raw)
        self.assertEqual(proposal.operations[0].op, "create_stage_channel")
        self.assertFalse(build_plan_diff(proposal, inv, plan_hash(proposal)).blocked)

    def test_stage_duplicate_not_created(self):
        inv = self.inventory()
        inv.channels.append(ChannelSnap(200, "stage", "stage", category_id=2))
        self.assertIsNone(build_stage_proposal(inv, now_unix=100, community_enabled=True))

    def test_bounded_moves_and_stale_digest(self):
        inv = self.inventory()
        raw = build_move_batch(inv, now_unix=100, max_moves=2)
        self.assertLessEqual(len(raw["operations"]), 2)
        proposal = parse_proposal(raw)
        inv.channels[0] = ChannelSnap(1567827003414159365, "renamed", "text", category_id=10)
        self.assertTrue(build_plan_diff(proposal, inv, plan_hash(proposal)).blocked)


if __name__ == "__main__":
    unittest.main()
