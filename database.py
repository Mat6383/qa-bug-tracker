"""
Base de données SQLite — gestion des matrices et lignes par ticket.
"""

import sqlite3
from datetime import datetime
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=15,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Table des matrices
    c.execute("""
        CREATE TABLE IF NOT EXISTS risk_matrices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL DEFAULT '',
            version     TEXT    NOT NULL DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_id   INTEGER,
            FOREIGN KEY (parent_id) REFERENCES risk_matrices(id)
        )
    """)

    # Migration : ajout colonne name si absente
    try:
        c.execute("ALTER TABLE risk_matrices ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass

    # Table des lignes (une ligne = un ticket GitLab)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matrix_rows (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            matrix_id           INTEGER NOT NULL,
            module              TEXT    NOT NULL DEFAULT '',
            fonctionnalite      TEXT    DEFAULT '',
            gitlab_iid          TEXT    DEFAULT '',
            impact_level        TEXT    NOT NULL DEFAULT 'non_defini',
            weight              INTEGER DEFAULT NULL,
            impact_description  TEXT    DEFAULT '',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (matrix_id) REFERENCES risk_matrices(id) ON DELETE CASCADE
        )
    """)

    # Migrations : ajout des nouvelles colonnes sur DB existante
    for col, definition in [
        ("weight",             "INTEGER DEFAULT NULL"),
        ("impact_description", "TEXT DEFAULT ''"),
    ]:
        try:
            c.execute(f"ALTER TABLE matrix_rows ADD COLUMN {col} {definition}")
        except Exception:
            pass

    conn.commit()
    conn.close()


# ─── Matrices ─────────────────────────────────────────────────────────────────

def get_all_matrices():
    conn = get_db()
    rows = conn.execute("""
        SELECT m.*, COUNT(r.id) AS row_count
        FROM risk_matrices m
        LEFT JOIN matrix_rows r ON r.matrix_id = m.id
        GROUP BY m.id
        ORDER BY m.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_matrix(name, version, parent_id=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO risk_matrices (name, version, parent_id) VALUES (?, ?, ?)",
        (name, version, parent_id)
    )
    matrix_id = c.lastrowid

    # Héritage des lignes du parent
    if parent_id:
        c.execute("""
            INSERT INTO matrix_rows (matrix_id, module, fonctionnalite, gitlab_iid, impact_level)
            SELECT ?, module, fonctionnalite, gitlab_iid, impact_level
            FROM matrix_rows WHERE matrix_id = ?
        """, (matrix_id, parent_id))

    conn.commit()
    conn.close()
    return matrix_id


def get_matrix(matrix_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM risk_matrices WHERE id = ?", (matrix_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_matrix(matrix_id):
    conn = get_db()
    conn.execute("DELETE FROM risk_matrices WHERE id = ?", (matrix_id,))
    conn.commit()
    conn.close()


# ─── Lignes ───────────────────────────────────────────────────────────────────

def get_matrix_rows(matrix_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM matrix_rows WHERE matrix_id = ? ORDER BY module, id",
        (matrix_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_matrix_row(matrix_id, module, fonctionnalite="", gitlab_iid="",
                   impact_level="non_defini", weight=None, impact_description=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matrix_rows
            (matrix_id, module, fonctionnalite, gitlab_iid, impact_level, weight, impact_description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (matrix_id, module, fonctionnalite, gitlab_iid, impact_level, weight, impact_description))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_row_impact(row_id, impact_level):
    conn = get_db()
    conn.execute("UPDATE matrix_rows SET impact_level = ? WHERE id = ?", (impact_level, row_id))
    conn.commit()
    conn.close()


def delete_row(row_id):
    conn = get_db()
    conn.execute("DELETE FROM matrix_rows WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
