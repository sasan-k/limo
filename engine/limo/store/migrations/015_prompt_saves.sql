CREATE TABLE prompt_saves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent TEXT NOT NULL,
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('save', 'rollback')),
  created_at TEXT NOT NULL
);
