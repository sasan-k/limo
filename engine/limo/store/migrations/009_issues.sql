CREATE TABLE issues (
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  number INTEGER NOT NULL,
  url TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (project_id, feature, ticket)
);
