import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "validator",
    ROOT / "tools/validate-discord-copy.py",
)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def source():
    return [
        v.load(ROOT / p)
        for p in (
            "discord-server-copy/manifest.json",
            "discord-server-copy/existing-channel-map.json",
            "discord-server-copy/"
            "existing-channel-inventory.example.json",
        )
    ]


def populated():
    # Synthetic local fixtures only.
    # NOT actual guild/channel IDs or verified videos.
    m, mapping, inv = source()

    inv["guild_id"] = "100000000000000001"

    for index, c in enumerate(
        m["categories"], 1
    ):
        cid = str(
            200000000000000000 + index
        )
        inv["categories"].append({
            "id": cid,
            "name": "Fixture " + c["key"],
        })
        mapping["category_map"][
            index - 1
        ]["existing_category_id"] = cid

    categories = {
        c["category_key"]:
            c["existing_category_id"]
        for c in mapping["category_map"]
    }

    for index, c in enumerate(
        m["channels"], 1
    ):
        cid = str(
            300000000000000000 + index
        )
        mapping["channel_map"][
            index - 1
        ]["existing_channel_id"] = cid

        inv["channels"].append({
            "id": cid,
            "name": (
                "fixture-existing-" + str(index)
            ),
            "category_id": categories[
                c["category_key"]
            ],
            "kind": "text",
            "permissions_reviewed": True,
            "member_posting": (
                "denied"
                if c["read_only"]
                else "allowed"
            ),
            "private_content_reviewed": True,
        })

        if c["environment_binding"]:
            mapping["configured_intake_ids"][
                c["environment_binding"]
            ] = cid

    for video in m["videos"]:
        video.update(
            url=(
                "https://video.example.org/"
                "watch?v=synthetic-fixture"
            ),
            url_status="resolved",
            approved=True,
        )

    return m, mapping, inv


def copy_fixture(
    root,
    manifest,
    placeholder=False,
):
    # Minimal synthetic test text.
    # Not copies of the real onboarding documents.
    for d in manifest["copy_documents"]:
        p = Path(root) / d["path"]
        p.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        p.write_text(
            "SYNTHETIC TEST COPY\n"
            + d["label"]
            + (
                "\n{{UNRESOLVED_FIXTURE}}"
                if placeholder
                else ""
            ),
            encoding="utf-8",
        )


class ManifestTests(unittest.TestCase):
    def test_original_draft_valid_but_not_ready(self):
        r = v.validate(*source())

        self.assertTrue(
            r["structurally_valid"]
        )
        self.assertFalse(
            r["handoff_ready"]
        )
        self.assertEqual(
            r["unresolved_video_entries"], 26
        )
        self.assertEqual(
            r["active_categories"], 6
        )
        self.assertEqual(
            r["channels"], 11
        )

    def test_stable_keys_cannot_silently_change(self):
        m, a, i = source()
        m["channels"][0]["key"] = (
            "start_here.replacement"
        )
        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_exactly_one_conversation_per_category(self):
        m, a, i = source()
        m["channels"][0]["kind"] = "discussion"
        m["channels"][0]["read_only"] = False

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_read_only_intake_and_information_policy(self):
        for key in (
            "start_here.page",
            "feedback.bugs",
        ):
            m, a, i = source()
            c = next(
                c for c in m["channels"]
                if c["key"] == key
            )
            c["read_only"] = not c["read_only"]

            with self.assertRaises(v.Invalid):
                v.validate(m, a, i)

    def test_duplicate_keys_and_unknown_fields(self):
        m, a, i = source()
        m["videos"].append(
            copy.deepcopy(m["videos"][0])
        )

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

        m, a, i = source()
        m["channels"][0][
            "create_if_missing"
        ] = True

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_unresolved_video_is_explicit_null_and_unapproved(self):
        for change in (
            {
                "url":
                    "https://video.example.org/x"
            },
            {"approved": True},
            {
                "transcript_url":
                    "https://video.example.org/x"
            },
        ):
            m, a, i = source()
            m["videos"][0].update(change)

            with self.assertRaises(v.Invalid):
                v.validate(m, a, i)

    def test_resolved_video_requires_approval(self):
        m, a, i = populated()
        m["videos"][0]["approved"] = False

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_unsafe_video_urls_rejected(self):
        for url in (
            "http://video.example.org/x",
            "javascript:alert(1)",
            "https://user:password@video.example.org/x",
            "https://127.0.0.1/x",
            "https://video.example.org/x"
            "?access_token=synthetic",
            "https://video.example.org/x#secret",
            "https://host.local/x",
        ):
            with self.assertRaises(v.Invalid):
                v.video_url(url)

    def test_normal_https_watch_query_allowed_without_network(self):
        v.video_url(
            "https://video.example.org/"
            "watch?v=synthetic&t=42"
        )

    def test_dangling_video_and_binding_changes_rejected(self):
        m, a, i = source()
        m["channels"][2][
            "video_keys"
        ].append("unknown.video")

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

        m, a, i = source()
        next(
            c for c in m["channels"]
            if c["key"] == "feedback.bugs"
        )["environment_binding"] = None

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_reuse_preserves_names_and_all_settings(self):
        m, a, i = populated()
        before = copy.deepcopy((m, a, i))

        with tempfile.TemporaryDirectory() as tmp:
            copy_fixture(tmp, m)
            result = v.validate(
                m, a, i, tmp
            )

        self.assertTrue(
            result["handoff_ready"]
        )
        self.assertEqual(
            (m, a, i), before
        )
        self.assertTrue(all(
            not x["rename"]
            and not x["move"]
            and not x["change_permissions"]
            for x in result["reuse"]
        ))
        self.assertTrue(
            result["reuse"][0][
                "existing_name"
            ].startswith(
                "fixture-existing-"
            )
        )

    def test_same_channel_cannot_fill_two_targets(self):
        m, a, i = populated()
        a["channel_map"][1][
            "existing_channel_id"
        ] = a["channel_map"][0][
            "existing_channel_id"
        ]

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_wrong_category_cannot_imply_automatic_move(self):
        m, a, i = populated()
        i["channels"][0][
            "category_id"
        ] = i["categories"][1]["id"]

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_existing_intake_binding_cannot_be_reassigned(self):
        m, a, i = populated()
        a["configured_intake_ids"][
            "GN_BUGS_CHANNEL_ID"
        ] = "999999999999999999"

        with self.assertRaises(v.Invalid):
            v.validate(m, a, i)

    def test_permissions_are_operator_attestation_not_assumed(self):
        m, a, i = populated()
        i["channels"][0][
            "permissions_reviewed"
        ] = False
        i["channels"][0][
            "private_content_reviewed"
        ] = False

        r = v.validate(m, a, i)

        self.assertTrue(any(
            "posting policy" in b
            for b in r["blockers"]
        ))
        self.assertTrue(any(
            "private-content" in b
            for b in r["blockers"]
        ))

    def test_copy_placeholders_block_ready_and_coming_soon_is_required(self):
        m, a, i = populated()

        with tempfile.TemporaryDirectory() as tmp:
            copy_fixture(
                tmp, m, placeholder=True
            )
            self.assertFalse(
                v.validate(
                    m, a, i, tmp
                )["handoff_ready"]
            )

            copy_fixture(tmp, m)

            preview = next(
                d for d in m["copy_documents"]
                if d["key"]
                == "algo_lab_preview"
            )
            (
                Path(tmp) / preview["path"]
            ).write_text(
                "SYNTHETIC TEST: missing status label"
            )

            with self.assertRaises(v.Invalid):
                v.validate(m, a, i, tmp)

    def test_duplicate_json_properties_and_nonfinite_values_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"

            for raw in (
                '{"key":1,"key":2}',
                '{"key":NaN}',
                "{",
            ):
                p.write_text(raw)

                with self.assertRaises(v.Invalid):
                    v.load(p)

    def test_cli_draft_and_ready_exit_codes(self):
        script = str(
            ROOT / "tools/validate-discord-copy.py"
        )

        for extra, expected in (
            ([], 0),
            (["--ready"], 1),
        ):
            r = subprocess.run(
                [
                    sys.executable,
                    script,
                    *extra,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                r.returncode,
                expected,
                r.stderr,
            )
            self.assertFalse(
                json.loads(
                    r.stdout
                )["handoff_ready"]
            )


if __name__ == "__main__":
    unittest.main()
