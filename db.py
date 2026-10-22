"""SQLite schema and helpers. Consent records are kept in a separate table
from responses; no names, e-mails or IP addresses are stored."""
import sqlite3
import os
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS allocation (
    stream      TEXT    NOT NULL,          -- 'real' or 'test'
    slot        INTEGER NOT NULL,
    block_no    INTEGER NOT NULL,
    condition   INTEGER NOT NULL CHECK (condition IN (0,1)),
    used_by     TEXT,                      -- study_code or NULL
    PRIMARY KEY (stream, slot)
);
CREATE TABLE IF NOT EXISTS participants (
    study_code    TEXT PRIMARY KEY,
    condition     INTEGER NOT NULL CHECK (condition IN (0,1)),
    alloc_slot    INTEGER NOT NULL,
    is_test       INTEGER NOT NULL DEFAULT 0,
    profile_order TEXT    NOT NULL,        -- e.g. "P3,P1,P6,P2,P5,P4"
    status        TEXT    NOT NULL DEFAULT 'started',  -- started|rated|completed
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    completed_at  TEXT
);
CREATE TABLE IF NOT EXISTS consent_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    study_code   TEXT NOT NULL,
    consented    INTEGER NOT NULL,
    is_student   INTEGER NOT NULL,
    age_18_25    INTEGER NOT NULL,
    dating_app   INTEGER NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS profiles (
    profile_id   TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    age          INTEGER NOT NULL,
    bio          TEXT NOT NULL,
    image_file   TEXT NOT NULL,
    image_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
    study_code  TEXT    NOT NULL REFERENCES participants(study_code),
    profile_id  TEXT    NOT NULL REFERENCES profiles(profile_id),
    position    INTEGER NOT NULL,          -- 1..6 order shown
    item_no     INTEGER NOT NULL,
    construct   TEXT    NOT NULL,
    value       INTEGER NOT NULL CHECK (value BETWEEN 1 AND 7),
    decision    TEXT    CHECK (decision IN ('like','skip')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (study_code, profile_id, item_no)
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    study_code  TEXT NOT NULL REFERENCES participants(study_code),
    profile_id  TEXT,
    event_type  TEXT NOT NULL,             -- view_start|view_end|like|skip|label_hover|label_click
    value_ms    INTEGER,
    client_ts   INTEGER,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS post_survey (
    study_code   TEXT PRIMARY KEY REFERENCES participants(study_code),
    label_recall TEXT NOT NULL CHECK (label_recall IN ('yes','no','not_sure')),
    open_text    TEXT,
    gender       TEXT,
    study_year   TEXT,
    app_use_freq TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(con):
    con.executescript(SCHEMA)
    con.commit()
