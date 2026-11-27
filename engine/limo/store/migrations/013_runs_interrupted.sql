PRAGMA foreign_keys = OFF;
CREATE TABLE runs_new (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  agent TEXT NOT NULL,
  feature TEXT NOT NULL,
  ticket TEXT,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'interrupted')),
  model TEXT NOT NULL,
  output TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT,
  args TEXT,
  ticket_status TEXT,
  note TEXT,
  attempt INTEGER NOT NULL DEFAULT 1
);
INSERT INTO runs_new (id, project_id, agent, feature, ticket, status, model, output, error, created_at,
  finished_at, args, ticket_status, note)
  SELECT id, project_id, agent, feature, ticket, status, model, output, error, created_at,
  finished_at, args, ticket_status, note FROM runs;
DROP TABLE runs;
ALTER TABLE runs_new RENAME TO runs;
CREATE INDEX runs_project_agent ON runs (project_id, agent);
CREATE INDEX runs_status ON runs (status);
CREATE INDEX runs_project_feature_agent ON runs (project_id, feature, agent);
PRAGMA foreign_keys = ON;
