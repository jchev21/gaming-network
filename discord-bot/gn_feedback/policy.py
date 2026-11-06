import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit


@dataclass(frozen=True)
class Config:
    enabled: bool
    delivery: bool
    guild: int
    bugs: int
    suggestions: int
    database: str
    repository: str
    token: str
    hash_key: str

    @classmethod
    def from_env(cls):
        enabled = os.getenv("GN_FEEDBACK_ENABLED", "false") == "true"
        delivery = os.getenv("GN_FEEDBACK_GITHUB_ENABLED", "false") == "true"

        def snowflake(name):
            value = os.getenv(name, "")
            if not re.fullmatch(r"[1-9][0-9]{5,24}", value):
                if enabled:
                    raise ValueError(
                        "Feedback channel/guild configuration invalid"
                    )
                return 0
            return int(value)

        c = cls(
            enabled,
            delivery,
            snowflake("GN_FEEDBACK_GUILD_ID"),
            snowflake("GN_BUGS_CHANNEL_ID"),
            snowflake("GN_SUGGESTIONS_CHANNEL_ID"),
            os.getenv("GN_FEEDBACK_DB_PATH", "/data/gn-feedback.sqlite3"),
            "jchev21/gaming-network",
            os.getenv("GN_FEEDBACK_GITHUB_TOKEN", ""),
            os.getenv("GN_FEEDBACK_HASH_KEY", ""),
        )
        if enabled and (
            c.bugs == c.suggestions or len(c.hash_key) < 32
        ):
            raise ValueError(
                "Feedback isolation/hash configuration invalid"
            )
        if enabled and delivery and not c.token:
            raise ValueError("Feedback GitHub credential unavailable")
        return c


class Redactor:
    def __init__(self, secrets=()):
        self.secrets = sorted(
            {
                s for s in secrets
                if isinstance(s, str) and len(s) >= 8
            },
            key=len,
            reverse=True,
        )

    @classmethod
    def from_env(cls):
        return cls(
            v for k, v in os.environ.items()
            if re.search(
                r"TOKEN|SECRET|PASSWORD|COOKIE|KEY", k, re.I
            )
        )

    def clean(self, text):
        text = unquote(str(text))
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")

        text = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?"
            r"-----END [^-]*PRIVATE KEY-----",
            "[REDACTED KEY]",
            text,
            flags=re.S,
        )
        text = re.sub(
            r"(?i)\b(?:authorization|cookie|set-cookie|password|"
            r"api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"client[_-]?secret|redemption[_-]?code|join[_-]?code)"
            r"\s*[:=][^\r\n]*",
            "[REDACTED FIELD]",
            text,
        )
        text = re.sub(
            r"(?i)\bBearer\s+\S+|\bgh[pousr]_[A-Za-z0-9_]+|"
            r"\bgithub_pat_[A-Za-z0-9_]+|"
            r"\bsk-[A-Za-z0-9_-]{12,}|"
            r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}"
            r"\.[A-Za-z0-9_-]{20,}",
            "[REDACTED TOKEN]",
            text,
        )
        text = re.sub(
            r"https?://\S+",
            "[URL omitted; see original Discord message]",
            text,
        )
        text = re.sub(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            "[REDACTED EMAIL]",
            text,
        )
        text = re.sub(
            r"<[@#][!&]?[0-9]+>",
            "[Discord mention]",
            text,
        )
        text = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
            "",
            text,
        )
        return (
            text.replace("@", "＠")
            .replace("`", "ˋ")
            .replace("<", "‹")
            .replace(">", "›")[:4000]
        )

    def attachments(self, attachments):
        out = []
        for a in attachments[:4]:
            suffix = str(a.filename).rsplit(".", 1)[-1].lower()
            if (
                suffix not in {
                    "png", "jpg", "jpeg", "webp", "txt", "log"
                }
                or not 0 < a.size <= 2097152
            ):
                continue

            allowed_mime = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "webp": "image/webp",
                "txt": "text/plain",
                "log": "text/plain",
            }
            if getattr(a, "content_type", None) not in {
                None, allowed_mime[suffix]
            }:
                continue

            try:
                u = urlsplit(str(a.url))
                port = u.port
            except ValueError:
                continue

            if (
                u.scheme != "https"
                or u.hostname not in {
                    "cdn.discordapp.com", "media.discordapp.net"
                }
                or u.username
                or u.password
                or port not in {None, 443}
                or not re.fullmatch(
                    r"/attachments/[0-9]+/[0-9]+/"
                    r"[A-Za-z0-9_.-]{1,80}",
                    u.path,
                )
            ):
                continue

            if not u.path.lower().endswith("." + suffix):
                continue

            url = urlunsplit(
                (u.scheme, u.netloc, u.path, "", "")
            )
            if (
                any(s in url for s in self.secrets)
                or re.search(
                    r"gh[pousr]_|github_pat_|sk-", url
                )
            ):
                continue
            out.append(url)
        return out


def member_key(key, guild, user):
    return hmac.new(
        key.encode(),
        f"{guild}:{user}".encode(),
        hashlib.sha256,
    ).hexdigest()


def fingerprint(kind, channel, text, attachments):
    # Exact normalized deduplication, not fuzzy incident merging.
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(
        f"{kind}:{channel}:{normalized}:{attachments}".encode()
    ).hexdigest()
