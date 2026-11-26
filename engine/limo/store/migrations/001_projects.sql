CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  git_url TEXT NOT NULL,
  host TEXT NOT NULL CHECK (host IN ('github', 'gitlab')),
  status TEXT NOT NULL,
  default_branch TEXT NOT NULL,
  workspace TEXT NOT NULL,
  created_at TEXT NOT NULL
);
