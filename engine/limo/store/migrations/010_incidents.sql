CREATE TABLE incidents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  k INTEGER NOT NULL,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'needs_human')),
  run_id TEXT,
  resolver_run_id TEXT,
  action TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX incidents_feature ON incidents (project_id, feature, status);
ALTER TABLE runs ADD COLUMN ticket_status TEXT;
