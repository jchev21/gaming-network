#!/usr/bin/env python3
"""Offline validation only. No Discord client, network, environment lookup or edits."""

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

NAMESPACE = "gaming_network.discord_copy.v1"
MAX_BYTES = 2097152

CATEGORY_KEYS = {
    "start_here",
    "community",
    "games_x",
    "algo_lab",
    "education",
    "accounts_providers",
    "feedback",
}

CHANNEL_KEYS = {
    "start_here.page",
    "start_here.rules",
    "start_here.help",
    "community.discussion",
    "games_x.discussion",
    "algo_lab.discussion",
    "education.discussion",
    "accounts_providers.discussion",
    "feedback.bugs",
    "feedback.suggestions",
    "feedback.discussion",
}

KEY = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
)
ID = re.compile(r"^[1-9][0-9]{14,21}$")

BINDINGS = {
    "feedback.bugs": "GN_BUGS_CHANNEL_ID",
    "feedback.suggestions": "GN_SUGGESTIONS_CHANNEL_ID",
}


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def fields(value, keys):
    require(
        isinstance(value, dict)
        and set(value) == set(keys.split()),
        "Unexpected or missing fields",
    )


def text(value, maximum):
    require(
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and value.strip()
        and not re.search(
            r"[\x00-\x1f\x7f]", value
        ),
        "Invalid bounded text",
    )


def flag(value):
    require(
        type(value) is bool,
        "Expected explicit boolean",
    )


def identifier(value, nullable=False):
    require(
        nullable and value is None
        or isinstance(value, str)
        and ID.fullmatch(value),
        "Invalid Discord ID",
    )


def records(value, key="key"):
    require(
        isinstance(value, list)
        and len(value) <= 100,
        "Invalid bounded record list",
    )
    result = {}
    for item in value:
        require(
            isinstance(item, dict),
            "Invalid record",
        )
        name = item.get(key)
        require(
            isinstance(name, str)
            and KEY.fullmatch(name)
            and name not in result,
            "Invalid or duplicate stable key",
        )
        result[name] = item
    return result


def video_url(value):
    text(value, 2048)
    try:
        u = urlsplit(value)
        require(
            u.scheme == "https"
            and u.hostname
            and not u.username
            and not u.password
            and u.port in (None, 443)
            and not u.fragment
            and not re.search(
                r"[\s<>\\]", value
            ),
            "Unsafe video URL",
        )

        host = u.hostname.lower()
        require(
            "." in host
            and not host.endswith(
                (".local", ".localhost", ".internal")
            ),
            "Unsafe video host",
        )

        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise Invalid(
                "IP-literal video hosts are not allowed"
            )

        for key, _ in parse_qsl(
            u.query, keep_blank_values=True
        ):
            require(
                not re.search(
                    r"token|secret|password|signature|"
                    r"credential|api.?key|redemption|x-amz",
                    key,
                    re.I,
                ),
                "Credential-bearing video query refused",
            )

    except (ValueError, UnicodeError):
        raise Invalid(
            "Unsafe video URL"
        ) from None


def validate(
    manifest,
    mapping,
    inventory,
    copy_root=None,
):
    fields(
        manifest,
        "schema_version key_namespace mode "
        "permissions_are categories channels "
        "videos copy_documents",
    )
    require(
        type(manifest["schema_version"]) is int
        and manifest["schema_version"] == 1,
        "Unsupported manifest version",
    )
    require(
        manifest["key_namespace"] == NAMESPACE
        and manifest["mode"] == "offline_draft"
        and manifest["permissions_are"]
        == "proposed_not_observed",
        "Manifest policy changed",
    )

    cats = records(manifest["categories"])
    channels = records(manifest["channels"])
    videos = records(manifest["videos"])
    docs = records(manifest["copy_documents"])

    require(
        set(cats) == CATEGORY_KEYS
        and set(channels) == CHANNEL_KEYS
        and docs,
        "Version 1 stable keys changed",
    )

    proposed = set()
    pins = set()
    discussions = {
        key: 0 for key in cats
    }

    for c in cats.values():
        fields(
            c, "key proposed_name optional"
        )
        text(c["proposed_name"], 100)
        flag(c["optional"])
        require(
            c["optional"]
            == (c["key"] == "accounts_providers"),
            "Optional-category policy changed",
        )

    for c in channels.values():
        fields(
            c,
            "key category_key proposed_name kind "
            "read_only topic pin_key video_keys "
            "environment_binding",
        )
        require(
            c["category_key"] in cats
            and c["category_key"]
            == c["key"].split(".")[0],
            "Unknown or changed category reference",
        )

        name = c["proposed_name"]
        require(
            isinstance(name, str)
            and len(name) <= 100
            and re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*",
                name,
            )
            and name not in proposed,
            "Invalid or duplicate proposed channel name",
        )
        proposed.add(name)

        require(
            c["kind"] in (
                "information",
                "discussion",
                "intake",
            ),
            "Unknown channel kind",
        )

        expected_kind = (
            "information"
            if c["key"] in (
                "start_here.page",
                "start_here.rules",
            )
            else "intake"
            if c["key"] in BINDINGS
            else "discussion"
        )
        require(
            c["kind"] == expected_kind,
            "Stable channel purpose changed",
        )

        flag(c["read_only"])
        require(
            c["read_only"]
            == (c["kind"] == "information"),
            "Read-only flag contradicts channel purpose",
        )
        text(c["topic"], 1024)

        require(
            isinstance(c["video_keys"], list)
            and len(c["video_keys"]) <= 20
            and len(set(c["video_keys"]))
            == len(c["video_keys"])
            and all(
                k in videos
                for k in c["video_keys"]
            ),
            "Invalid video references",
        )

        require(
            c["environment_binding"]
            == BINDINGS.get(c["key"]),
            "Intake binding changed",
        )

        if c["kind"] == "discussion":
            discussions[c["category_key"]] += 1
            require(
                c["pin_key"]
                == c["key"] + ".video_index"
                and c["pin_key"] not in pins,
                "Invalid pin key",
            )
            pins.add(c["pin_key"])
        else:
            require(
                c["pin_key"] is None
                and not c["video_keys"],
                "Only the category conversation channel "
                "receives the video index",
            )

    require(
        all(
            n == 1
            for n in discussions.values()
        ),
        "Each category must define exactly "
        "one conversation channel",
    )

    for v in videos.values():
        fields(
            v,
            "key title url url_status "
            "url_placeholder approved transcript_url",
        )
        text(v["title"], 160)
        require(
            isinstance(
                v["url_placeholder"], str
            )
            and re.fullmatch(
                r"\{\{VIDEO_[A-Z0-9_]+_URL\}\}",
                v["url_placeholder"],
            ),
            "Invalid video placeholder",
        )
        flag(v["approved"])

        if v["url_status"] == "unresolved":
            require(
                v["url"] is None
                and not v["approved"]
                and v["transcript_url"] is None,
                "Unresolved video must have null URL "
                "and no approval",
            )
        else:
            require(
                v["url_status"] == "resolved"
                and v["approved"],
                "Resolved video requires explicit "
                "operator approval",
            )
            video_url(v["url"])

            if v["transcript_url"] is not None:
                video_url(v["transcript_url"])

    require(
        len({
            v["url_placeholder"]
            for v in videos.values()
        }) == len(videos),
        "Duplicate video placeholder",
    )

    paths = set()
    for d in docs.values():
        fields(
            d, "key path label video_keys"
        )
        require(
            isinstance(d["path"], str)
            and re.fullmatch(
                r"discord-server-copy/"
                r"[A-Z][A-Z0-9_]*\.md",
                d["path"],
            )
            and d["path"] not in paths,
            "Invalid or duplicate copy path",
        )
        paths.add(d["path"])

        require(
            d["label"] in (
                "ONBOARDING",
                "PROPOSED",
                "TEMPLATE",
                "COMING SOON",
            ),
            "Invalid copy label",
        )
        require(
            isinstance(d["video_keys"], list)
            and len(d["video_keys"]) <= 20
            and len(set(d["video_keys"]))
            == len(d["video_keys"])
            and all(
                k in videos
                for k in d["video_keys"]
            ),
            "Invalid copy video reference",
        )

    for key in (
        "algo_lab_preview",
        "education_preview",
    ):
        require(
            key in docs
            and docs[key]["label"]
            == "COMING SOON",
            "Planned preview must stay "
            "labelled Coming Soon",
        )

    fields(
        mapping,
        "schema_version manifest_namespace policy "
        "category_map channel_map configured_intake_ids",
    )
    require(
        type(mapping["schema_version"]) is int
        and mapping["schema_version"] == 1
        and mapping["manifest_namespace"]
        == NAMESPACE
        and mapping["policy"]
        == "reuse_only_no_mutations",
        "Invalid mapping policy/version",
    )

    cm = records(
        mapping["category_map"],
        "category_key",
    )
    chm = records(
        mapping["channel_map"],
        "channel_key",
    )
    require(
        set(cm) == set(cats)
        and set(chm) == set(channels),
        "Mapping must cover every stable key",
    )

    fields(
        mapping["configured_intake_ids"],
        "GN_BUGS_CHANNEL_ID "
        "GN_SUGGESTIONS_CHANNEL_ID",
    )
    for value in (
        mapping["configured_intake_ids"].values()
    ):
        identifier(value, True)

    fields(
        inventory,
        "schema_version guild_id "
        "categories channels",
    )
    require(
        type(inventory["schema_version"]) is int
        and inventory["schema_version"] == 1,
        "Unsupported inventory version",
    )
    identifier(
        inventory["guild_id"], True
    )
    require(
        isinstance(
            inventory["categories"], list
        )
        and len(inventory["categories"]) <= 100
        and isinstance(
            inventory["channels"], list
        )
        and len(inventory["channels"]) <= 500,
        "Inventory too large",
    )

    ic, ich = {}, {}
    all_ids = set()

    for c in inventory["categories"]:
        fields(c, "id name")
        identifier(c["id"])
        text(c["name"], 100)
        require(
            c["id"] not in all_ids,
            "Duplicate inventory ID",
        )
        all_ids.add(c["id"])
        ic[c["id"]] = c

    for c in inventory["channels"]:
        fields(
            c,
            "id name category_id kind "
            "permissions_reviewed member_posting "
            "private_content_reviewed",
        )
        identifier(c["id"])
        identifier(c["category_id"])
        text(c["name"], 100)
        flag(c["permissions_reviewed"])
        flag(c["private_content_reviewed"])
        require(
            c["id"] not in all_ids
            and c["category_id"] in ic
            and c["kind"] == "text"
            and c["member_posting"] in (
                "unknown",
                "allowed",
                "denied",
            ),
            "Invalid inventory channel",
        )
        all_ids.add(c["id"])
        ich[c["id"]] = c

    blockers, reuse = [], []

    if inventory["guild_id"] is None:
        blockers.append(
            "inventory.guild_id unresolved"
        )

    used_categories = set()
    used_channels = set()
    active = set()

    for key, item in cm.items():
        fields(
            item,
            "category_key include "
            "existing_category_id",
        )
        flag(item["include"])
        identifier(
            item["existing_category_id"],
            True,
        )
        require(
            item["include"]
            or cats[key]["optional"],
            "Required category cannot be excluded",
        )

        value = item["existing_category_id"]
        if value is not None:
            require(
                value in ic
                and value not in used_categories,
                "Unknown or multiply reused category ID",
            )
            used_categories.add(value)

        if item["include"]:
            active.add(key)
            if value is None:
                blockers.append(
                    "category mapping unresolved: " + key
                )

    referenced = set()

    for key, item in chm.items():
        fields(
            item,
            "channel_key existing_channel_id name_hints",
        )
        identifier(
            item["existing_channel_id"], True
        )
        require(
            isinstance(item["name_hints"], list)
            and 1 <= len(item["name_hints"]) <= 5,
            "Invalid name hints",
        )
        for hint in item["name_hints"]:
            text(hint, 100)

        value = item["existing_channel_id"]
        definition = channels[key]
        actual = None

        if value is not None:
            require(
                value in ich
                and value not in used_channels,
                "Unknown or multiply reused channel ID",
            )
            used_channels.add(value)
            actual = ich[value]

            category_id = cm[
                definition["category_key"]
            ]["existing_category_id"]

            require(
                category_id is not None
                and actual["category_id"]
                == category_id,
                "Reuse would require an "
                "unapproved category move",
            )

        if definition["category_key"] not in active:
            continue

        referenced.update(
            definition["video_keys"]
        )

        if actual is None:
            blockers.append(
                "channel mapping unresolved: " + key
            )
        else:
            expected = (
                "denied"
                if definition["read_only"]
                else "allowed"
            )
            if (
                not actual["permissions_reviewed"]
                or actual["member_posting"]
                != expected
            ):
                blockers.append(
                    "posting policy not confirmed: " + key
                )

            if not actual["private_content_reviewed"]:
                blockers.append(
                    "private-content review missing: "
                    + key
                )

            reuse.append({
                "key": key,
                "existing_id": value,
                "existing_name": actual["name"],
                "proposed_name":
                    definition["proposed_name"],
                "rename": False,
                "move": False,
                "change_permissions": False,
            })

        binding = definition["environment_binding"]
        if binding:
            configured = mapping[
                "configured_intake_ids"
            ][binding]

            if configured is None:
                blockers.append(
                    "existing intake binding unresolved: "
                    + binding
                )
            else:
                require(
                    configured == value,
                    "Intake mapping conflicts with "
                    "existing configured ID",
                )

    for d in docs.values():
        referenced.update(d["video_keys"])

    for key in sorted(referenced):
        if videos[key]["url_status"] != "resolved":
            blockers.append(
                "video URL unresolved: " + key
            )

    if copy_root is None:
        blockers.append(
            "copy files not checked; supply --copy-root"
        )
    else:
        base = Path(copy_root).resolve()

        for d in docs.values():
            path = (
                base / d["path"]
            ).resolve()

            require(
                path.is_relative_to(base),
                "Copy file escapes selected root",
            )

            try:
                with path.open("rb") as handle:
                    raw = handle.read(
                        MAX_BYTES + 1
                    )
                require(
                    len(raw) <= MAX_BYTES,
                    "Copy file too large",
                )
                content = raw.decode("utf-8")

            except (OSError, UnicodeError):
                blockers.append(
                    "copy file missing/unreadable: "
                    + d["key"]
                )
                continue

            if re.search(
                r"\{\{[A-Z][A-Z0-9_]*\}\}",
                content,
            ):
                blockers.append(
                    "unresolved copy placeholder: "
                    + d["key"]
                )

            if d["label"] == "COMING SOON":
                require(
                    "COMING SOON" in content,
                    "Coming Soon copy label removed",
                )

    return {
        "structurally_valid": True,
        "handoff_ready": not blockers,
        "categories": len(cats),
        "active_categories": len(active),
        "channels": len(channels),
        "unresolved_video_entries": sum(
            v["url_status"] == "unresolved"
            for v in videos.values()
        ),
        "blockers": blockers,
        "reuse": reuse,
        "notice": (
            "Offline consistency check only. "
            "IDs, permissions, URL existence and "
            "operator approvals are not verified "
            "against Discord or video providers. "
            "No mutations are performed."
        ),
    }


def load(filename):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(
                key not in result,
                "Duplicate JSON property",
            )
            result[key] = value
        return result

    try:
        with Path(filename).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)

        require(
            len(raw) <= MAX_BYTES,
            "JSON file too large",
        )

        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda _: (
                _ for _ in ()
            ).throw(
                Invalid(
                    "Non-finite JSON constant"
                )
            ),
        )

    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
    ):
        raise Invalid(
            "Unreadable or malformed bounded JSON input"
        ) from None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--manifest",
        default="discord-server-copy/manifest.json",
    )
    parser.add_argument(
        "--mapping",
        default=(
            "discord-server-copy/"
            "existing-channel-map.json"
        ),
    )
    parser.add_argument(
        "--inventory",
        default=(
            "discord-server-copy/"
            "existing-channel-inventory.example.json"
        ),
    )
    parser.add_argument("--copy-root")
    parser.add_argument(
        "--ready",
        action="store_true",
        help="Exit 1 if handoff blockers remain",
    )
    args = parser.parse_args()

    try:
        result = validate(
            load(args.manifest),
            load(args.mapping),
            load(args.inventory),
            args.copy_root,
        )
    except (
        Invalid,
        TypeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        print(json.dumps({
            "structurally_valid": False,
            "handoff_ready": False,
            "error": (
                "Validation failed; check schemas, keys, "
                "mappings, safe URLs and policy constraints. "
                "Raw input is not logged."
            ),
        }))
        return 2

    print(json.dumps(result, indent=2))

    return (
        1
        if args.ready
        and not result["handoff_ready"]
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
