import json
import os
import sqlite3
import time
import uuid
import fcntl
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, filename):
        path = Path(filename)
        path.parent.mkdir(
            parents=True, exist_ok=True, mode=0o700
        )

        self.lock = open(str(path) + ".lock", "a+b")
        os.chmod(str(path) + ".lock", 0o600)
        try:
            fcntl.flock(
                self.lock,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except OSError:
            self.lock.close()
            raise RuntimeError(
                "Feedback store already owned by another process"
            ) from None

        fd = os.open(
            path, os.O_CREAT | os.O_RDWR, 0o600
        )
        os.close(fd)
        os.chmod(path, 0o600)

        self.db = sqlite3.connect(
            path, timeout=5, isolation_level=None
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")

        version = self.db.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        if version not in (0, 1):
            self.close()
            raise RuntimeError(
                "Unsupported feedback database schema"
            )

        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
          id TEXT PRIMARY KEY,
          fingerprint TEXT UNIQUE NOT NULL,
          kind TEXT NOT NULL,
          text TEXT NOT NULL,
          attachments TEXT NOT NULL,
          issue INTEGER,
          state TEXT NOT NULL DEFAULT 'pending',
          version INTEGER NOT NULL DEFAULT 1,
          attempts INTEGER NOT NULL DEFAULT 0,
          due REAL NOT NULL DEFAULT 0,
          error TEXT,
          created REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY,
          message TEXT UNIQUE NOT NULL,
          group_id TEXT NOT NULL REFERENCES groups(id),
          channel TEXT NOT NULL,
          url TEXT NOT NULL,
          member TEXT NOT NULL,
          created REAL NOT NULL,
          ack TEXT NOT NULL DEFAULT 'new'
        );

        CREATE INDEX IF NOT EXISTS reports_member_time
          ON reports(member,created);

        PRAGMA user_version=1;
        """)

        # Creation may have reached GitHub before a crash.
        # Never blindly repeat that POST.
        self.db.execute(
            "UPDATE groups SET state='uncertain' "
            "WHERE state='creating'"
        )
        self.db.execute(
            "UPDATE groups SET state='pending' "
            "WHERE state='claimed'"
        )

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def accept(
        self, *, message, channel, url, member,
        kind, text, attachments, digest, now=None
    ):
        now = time.time() if now is None else now
        with self.tx() as db:
            old = db.execute(
                "SELECT * FROM reports WHERE message=?",
                (str(message),),
            ).fetchone()
            if old:
                return dict(old)

            total = db.execute(
                "SELECT count(*) FROM reports"
            ).fetchone()[0]
            recent = db.execute(
                "SELECT count(*) FROM reports WHERE created>?",
                (now - 3600,),
            ).fetchone()[0]
            personal = db.execute(
                "SELECT count(*) FROM reports "
                "WHERE member=? AND created>?",
                (member, now - 600),
            ).fetchone()[0]

            if (
                total >= 10000
                or recent >= 30
                or personal >= 3
            ):
                raise ValueError(
                    "Feedback capacity/rate limit reached"
                )

            g = db.execute(
                "SELECT * FROM groups WHERE fingerprint=?",
                (digest,),
            ).fetchone()

            if not g:
                count = db.execute(
                    "SELECT count(*) FROM groups"
                ).fetchone()[0]
                queued = db.execute(
                    "SELECT count(*) FROM groups "
                    "WHERE state!='done'"
                ).fetchone()[0]
                if count >= 1000 or queued >= 200:
                    raise ValueError("Feedback queue full")

                gid = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO groups("
                    "id,fingerprint,kind,text,attachments,created"
                    ") VALUES(?,?,?,?,?,?)",
                    (
                        gid, digest, kind, text,
                        json.dumps(attachments), now,
                    ),
                )
            else:
                gid = g["id"]
                db.execute(
                    "UPDATE groups SET version=version+1,"
                    "state=CASE WHEN state='done' "
                    "THEN 'pending' ELSE state END WHERE id=?",
                    (gid,),
                )

            rid = uuid.uuid4().hex
            db.execute(
                "INSERT INTO reports("
                "id,message,group_id,channel,url,member,created"
                ") VALUES(?,?,?,?,?,?,?)",
                (
                    rid, str(message), gid,
                    str(channel), url, member, now,
                ),
            )
            return dict(
                db.execute(
                    "SELECT * FROM reports WHERE id=?",
                    (rid,),
                ).fetchone()
            )

    def ack_intent(self, rid):
        with self.tx() as db:
            return db.execute(
                "UPDATE reports SET ack='sending' "
                "WHERE id=? AND ack='new'",
                (rid,),
            ).rowcount == 1

    def ack_done(self, rid):
        self.db.execute(
            "UPDATE reports SET ack='sent' WHERE id=?",
            (rid,),
        )

    def claim(self, now=None):
        now = time.time() if now is None else now
        with self.tx() as db:
            row = db.execute(
                "SELECT * FROM groups "
                "WHERE state IN ('pending','uncertain') "
                "AND due<=? ORDER BY created LIMIT 1",
                (now,),
            ).fetchone()
            if not row:
                return None

            item = dict(row)
            db.execute(
                "UPDATE groups SET state='claimed' WHERE id=?",
                (item["id"],),
            )
            item["reports"] = [
                dict(r) for r in db.execute(
                    "SELECT id,url FROM reports "
                    "WHERE group_id=? "
                    "ORDER BY created,id LIMIT 10",
                    (item["id"],),
                )
            ]
            item["count"] = db.execute(
                "SELECT count(*) FROM reports WHERE group_id=?",
                (item["id"],),
            ).fetchone()[0]
            return item

    def creating(self, gid):
        self.db.execute(
            "UPDATE groups SET state='creating' WHERE id=?",
            (gid,),
        )

    def complete(self, item, number):
        with self.tx() as db:
            db.execute(
                "UPDATE groups SET issue=?,"
                "state=CASE WHEN version=? "
                "THEN 'done' ELSE 'pending' END,"
                "attempts=0,error=NULL,due=0 WHERE id=?",
                (number, item["version"], item["id"]),
            )

    def fail(
        self, item, code, retry=False,
        delay=60, uncertain=False, now=None
    ):
        now = time.time() if now is None else now
        attempts = item["attempts"] + 1
        state = "uncertain" if uncertain else "pending"
        if not retry or attempts >= 5:
            state = "dead"

        self.db.execute(
            "UPDATE groups SET state=?,attempts=?,"
            "due=?,error=? WHERE id=?",
            (
                state,
                attempts,
                now + max(delay, 30 * 2**attempts),
                code,
                item["id"],
            ),
        )

    def get(self, gid):
        row = self.db.execute(
            "SELECT * FROM groups WHERE id=?",
            (gid,),
        ).fetchone()
        return dict(row) if row else None

    def close(self):
        if getattr(self, "db", None):
            self.db.close()
            self.db = None
        if not self.lock.closed:
            self.lock.close()
