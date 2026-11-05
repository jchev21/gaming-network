-- Gaming Network X lobbies — transactional schema (SQLite)
-- Isolated prototype for grok/lobby-storage. Does not touch production JSON paths.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lobbies (
  id              TEXT PRIMARY KEY,
  owner_x_id      TEXT NOT NULL,
  title           TEXT NOT NULL,
  game            TEXT NOT NULL,
  platform        TEXT NOT NULL,
  mode            TEXT NOT NULL CHECK (mode IN ('first', 'lottery')),
  seats           INTEGER NOT NULL CHECK (seats BETWEEN 2 AND 8),
  round_seconds   INTEGER NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('open', 'ready', 'closed', 'cancelled')),
  created_at      INTEGER NOT NULL,
  entry_closes_at INTEGER NOT NULL,
  finalized_at    INTEGER,
  cancelled_at    INTEGER,
  source_post_id  TEXT,
  host_json       TEXT,          -- public host metadata (mode/region/crossplay/island)
  winners_json    TEXT NOT NULL DEFAULT '[]',  -- ordered x_id list
  withdrawn_json  TEXT NOT NULL DEFAULT '[]',
  removed_json    TEXT NOT NULL DEFAULT '[]',
  version         INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_lobbies_owner ON lobbies(owner_x_id);
CREATE INDEX IF NOT EXISTS idx_lobbies_status ON lobbies(status);
CREATE INDEX IF NOT EXISTS idx_lobbies_source ON lobbies(source_post_id);

CREATE TABLE IF NOT EXISTS lobby_entries (
  lobby_id  TEXT NOT NULL REFERENCES lobbies(id) ON DELETE CASCADE,
  x_id      TEXT NOT NULL,
  name      TEXT NOT NULL,
  joined_at INTEGER NOT NULL,
  PRIMARY KEY (lobby_id, x_id)
);

CREATE INDEX IF NOT EXISTS idx_entries_x ON lobby_entries(x_id);

CREATE TABLE IF NOT EXISTS lobby_waitlist (
  lobby_id  TEXT NOT NULL REFERENCES lobbies(id) ON DELETE CASCADE,
  x_id      TEXT NOT NULL,
  name      TEXT NOT NULL,
  joined_at INTEGER NOT NULL,
  position  INTEGER NOT NULL,   -- FIFO order
  PRIMARY KEY (lobby_id, x_id)
);

CREATE INDEX IF NOT EXISTS idx_waitlist_order ON lobby_waitlist(lobby_id, position);

CREATE TABLE IF NOT EXISTS invites (
  token_hash  TEXT PRIMARY KEY,  -- sha256 of the raw invite token
  post_id     TEXT NOT NULL,
  owner_x_id  TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL,
  used_at     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_invites_post ON invites(post_id);
CREATE INDEX IF NOT EXISTS idx_invites_owner ON invites(owner_x_id);

CREATE TABLE IF NOT EXISTS join_secrets (
  lobby_id     TEXT PRIMARY KEY REFERENCES lobbies(id) ON DELETE CASCADE,
  ciphertext   TEXT NOT NULL,   -- JSON from sealJoinInstructions (v, iv, tag, data)
  updated_at   INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '1');
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('migrated_from_json', '0');
