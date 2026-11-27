CREATE TABLE budget_defaults (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  ticket_micros INTEGER NOT NULL,
  agent_micros INTEGER NOT NULL
);

CREATE TABLE ticket_budgets (
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  agent TEXT NOT NULL,
  budget_micros INTEGER NOT NULL,
  PRIMARY KEY (project_id, feature, ticket, agent)
);

CREATE TABLE holds (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('budget')),
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  cleared_at TEXT
);
CREATE INDEX holds_open ON holds (project_id, feature, cleared_at);
CREATE INDEX usage_ticket_agent ON usage (project_id, feature, ticket, agent);
