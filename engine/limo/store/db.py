import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(path: Path) -> None:
    conn = connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        for sql_file in sorted(MIGRATIONS.glob("*.sql")):
            number = int(sql_file.name.split("_", 1)[0])
            if number <= current:
                continue
            conn.executescript(sql_file.read_text())
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
            conn.commit()
    finally:
        conn.close()
