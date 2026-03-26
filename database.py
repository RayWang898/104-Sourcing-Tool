import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "sourcing.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS industries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS positions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            industry_id INTEGER REFERENCES industries(id) ON DELETE CASCADE,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(name, industry_id)
        );

        -- A keyword belongs to one (industry, position) pair.
        -- industry_id / position_id can be NULL meaning "general / applies to all".
        CREATE TABLE IF NOT EXISTS keywords (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            term        TEXT NOT NULL,
            notes       TEXT,
            industry_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,
            position_id INTEGER REFERENCES positions(id)  ON DELETE SET NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- A project = one recruiting requisition.
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            company     TEXT,
            industry_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,
            position_id INTEGER REFERENCES positions(id)  ON DELETE SET NULL,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Candidates downloaded from 104 and cached locally.
        CREATE TABLE IF NOT EXISTS candidates (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_104_id TEXT UNIQUE,
            name             TEXT,
            age              INTEGER,
            education        TEXT,
            experience_years INTEGER,
            location         TEXT,
            current_title    TEXT,
            expected_salary  TEXT,
            skills           TEXT,
            raw_data         TEXT,   -- full JSON blob from 104
            snapshot_at      TEXT DEFAULT (datetime('now'))
        );

        -- Many-to-many: candidates saved to projects, with optional notes.
        CREATE TABLE IF NOT EXISTS candidate_projects (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
            project_id   INTEGER REFERENCES projects(id)   ON DELETE CASCADE,
            notes        TEXT,
            saved_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(candidate_id, project_id)
        );

        -- Auto-tagged keywords matched when a candidate is saved to a project.
        CREATE TABLE IF NOT EXISTS candidate_keywords (
            candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
            keyword_id   INTEGER REFERENCES keywords(id)   ON DELETE CASCADE,
            PRIMARY KEY (candidate_id, keyword_id)
        );
    """)
    conn.commit()
    conn.close()


def setting_get(key: str, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def setting_set(key: str, value: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
