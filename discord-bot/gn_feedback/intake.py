import asyncio
import time
import logging

from .policy import (
    Config, Redactor, fingerprint, member_key
)
from .store import Store
from .github import Delivery, GitHub


class FeedbackIntake:
    """Additional listener; never replace bot.on_message."""

    def __init__(
        self, bot, config, redactor,
        store, delivery=None
    ):
        self.bot = bot
        self.config = config
        self.redactor = redactor
        self.store = store
        self.delivery = delivery
        self.task = None
        self.notice_at = {}

    async def notice(self, message):
        now = time.monotonic()
        if (
            now - self.notice_at.get(
                message.channel.id, -1e9
            ) < 60
        ):
            return
        self.notice_at[message.channel.id] = now

        try:
            import discord

            await message.reply(
                "Report not recorded: use at most "
                "4000 characters, four permitted "
                "attachments, and respect the feedback "
                "rate/capacity limits. Never include secrets.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "feedback_notice_failed"
            )

    async def on_message(self, message):
        c = self.config
        if (
            not c.enabled
            or message.author.bot
            or getattr(message, "webhook_id", None)
            or not message.guild
            or message.guild.id != c.guild
            or message.channel.id not in {
                c.bugs, c.suggestions
            }
        ):
            return

        age = (
            time.time()
            - message.created_at.timestamp()
        )
        if not 0 <= age <= 86400:
            return

        if (
            len(message.content) > 4000
            or len(message.attachments) > 4
        ):
            await self.notice(message)
            return

        try:
            text = self.redactor.clean(
                message.content
            )
            attachments = self.redactor.attachments(
                message.attachments
            )

            if not text.strip() and not attachments:
                await self.notice(message)
                return

            kind = (
                "bug"
                if message.channel.id == c.bugs
                else "suggestion"
            )
            url = (
                "https://discord.com/channels/"
                f"{c.guild}/{message.channel.id}/{message.id}"
            )
            report = self.store.accept(
                message=message.id,
                channel=message.channel.id,
                url=url,
                member=member_key(
                    c.hash_key,
                    c.guild,
                    message.author.id,
                ),
                kind=kind,
                text=text,
                attachments=attachments,
                digest=fingerprint(
                    kind,
                    message.channel.id,
                    text,
                    attachments,
                ),
            )

            if not self.store.ack_intent(
                report["id"]
            ):
                return

            # Lazy import keeps core tests dependency-free.
            import discord

            await message.reply(
                f"Recorded {kind} report "
                f"`{report['id'][:12]}` for triage. "
                "This is not a confirmed defect or "
                "implementation approval. "
                "Tracking stays here in Discord; "
                "no account secrets are needed.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
            self.store.ack_done(report["id"])

        except ValueError:
            await self.notice(message)

        except Exception:
            logging.getLogger(__name__).warning(
                "feedback_intake_failed"
            )
            # Never log raw Discord text, attachments,
            # credentials or upstream exceptions.
            # Receipts and send intent remain durable.
            return

    async def run(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                if self.delivery:
                    await self.delivery.once()
            except Exception:
                logging.getLogger(__name__).warning(
                    "feedback_outbox_failed"
                )
            await asyncio.sleep(2)

    def start(self):
        if not getattr(
            getattr(self.bot, "intents", None),
            "message_content",
            False,
        ):
            raise RuntimeError(
                "Feedback requires approved "
                "Message Content intent"
            )

        if not callable(
            getattr(self.bot, "add_listener", None)
        ):
            raise RuntimeError(
                "Feedback requires discord.py "
                "commands.Bot listener support"
            )

        if self.task is not None:
            raise RuntimeError(
                "Feedback listener already started"
            )

        self.bot.add_listener(
            self.on_message, "on_message"
        )
        self.task = asyncio.create_task(
            self.run(),
            name="gn-feedback-outbox",
        )

    async def stop(self):
        self.bot.remove_listener(
            self.on_message, "on_message"
        )
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Network threads use no database.
        # Cancelled write intent stays recoverable.
        if self.delivery:
            async with self.delivery.lock:
                pass

        self.store.close()


def build_feedback(bot):
    config = Config.from_env()
    if not config.enabled:
        return None

    store = Store(config.database)
    delivery = (
        Delivery(store, GitHub(config.token))
        if config.delivery else None
    )
    return FeedbackIntake(
        bot,
        config,
        Redactor.from_env(),
        store,
        delivery,
    )
