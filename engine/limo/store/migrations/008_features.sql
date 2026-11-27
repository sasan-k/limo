CREATE TABLE features (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  phase TEXT NOT NULL CHECK (phase IN ('architecture', 'spec', 'nfr', 'tickets')),
  created_at TEXT NOT NULL,
  UNIQUE (project_id, name)
);
ALTER TABLE runs ADD COLUMN args TEXT;
CREATE INDEX runs_project_feature_agent ON runs (project_id, feature, agent);
