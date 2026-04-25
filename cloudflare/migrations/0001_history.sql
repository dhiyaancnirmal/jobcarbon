CREATE TABLE IF NOT EXISTS anonymous_sessions (
  id TEXT PRIMARY KEY,
  cookie_token_hash TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_history (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  url TEXT NOT NULL,
  result_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_history_session_created_at
ON search_history (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_history_session_url
ON search_history (session_id, url);
