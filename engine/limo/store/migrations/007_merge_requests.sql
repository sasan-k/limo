CREATE TABLE merge_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  number INTEGER NOT NULL,
  url TEXT NOT NULL,
  branch TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('open', 'merged', 'closed')),
  last_review_id TEXT NOT NULL DEFAULT '',
  needs_push INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX merge_requests_feature ON merge_requests (project_id, feature, state);
