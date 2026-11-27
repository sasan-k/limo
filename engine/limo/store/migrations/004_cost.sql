CREATE TABLE prices (
  model TEXT PRIMARY KEY,
  input_micros INTEGER NOT NULL,
  output_micros INTEGER NOT NULL,
  cache_read_micros INTEGER NOT NULL,
  cache_write_micros INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  agent TEXT NOT NULL,
  feature TEXT NOT NULL,
  ticket TEXT,
  seq INTEGER NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL,
  cache_write_tokens INTEGER NOT NULL,
  cost_micros INTEGER NOT NULL,
  priced INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX usage_run ON usage (run_id);
CREATE INDEX usage_project ON usage (project_id);
