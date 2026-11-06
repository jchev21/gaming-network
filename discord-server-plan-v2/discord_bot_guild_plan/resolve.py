from __future__ import annotations
from dataclasses import dataclass

from .snapshot import GuildSnapshot, ChannelRecord, CategoryRecord


class AmbiguousMappingError(ValueError):
    """Fail closed: more than one channel or category matches a target name."""


@dataclass(frozen=True)
class Resolution:
    guild_id: int
    categories: dict
    channels: dict
    ambiguous: tuple = ()


def resolve_targets(
    snapshot: GuildSnapshot,
    target_category_names: list,
    target_channel_names: list,
    *,
    fail_closed: bool = True,
) -> Resolution:
    """Resolve template names to explicit IDs. Duplicate names fail closed."""
    cat_index: dict = {}
    for c in snapshot.categories:
        cat_index.setdefault(c.name.casefold(), []).append(c)

    ch_index: dict = {}
    for c in snapshot.channels:
        ch_index.setdefault(c.name.casefold(), []).append(c)

    ambiguous: list = []
    categories: dict = {}
    channels: dict = {}

    for name in target_category_names:
        hits = cat_index.get(name.casefold(), [])
        if len(hits) > 1:
            ambiguous.append(f"category:{name}\u2192{[h.id for h in hits]}")
            categories[name] = None
        elif len(hits) == 1:
            categories[name] = hits[0].id
        else:
            categories[name] = None

    for name in target_channel_names:
        hits = ch_index.get(name.casefold(), [])
        if len(hits) > 1:
            ambiguous.append(f"channel:{name}\u2192{[h.id for h in hits]}")
            channels[name] = None
        elif len(hits) == 1:
            channels[name] = hits[0].id
        else:
            channels[name] = None

    if ambiguous and fail_closed:
        raise AmbiguousMappingError(
            "Ambiguous name\u2192id mappings (fail closed): " + "; ".join(ambiguous)
        )

    return Resolution(
        guild_id=snapshot.guild_id,
        categories=categories,
        channels=channels,
        ambiguous=tuple(ambiguous),
    )
