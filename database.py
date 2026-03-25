import sqlite3
import os
from datetime import datetime
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_matrices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES risk_matrices(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS module_impacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matrix_id INTEGER NOT NULL,
            module_name TEXT NOT NULL,
            impact_level TEXT NOT NULL DEFAULT 'non_defini',
            comment TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (matrix_id) REFERENCES risk_matrices(id) ON DELETE CASCADE,
            UNIQUE(matrix_id, module_name)
        )
    """)

    conn.commit()
    conn.close()


# --- Matrices ---

def create_matrix(version, description="", parent_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO risk_matrices (version, description, parent_id) VALUES (?, ?, ?)",
        (version, description, parent_id),
    )
    matrix_id = cursor.lastrowid

    # Heriter des impacts de la matrice parente
    if parent_id:
        cursor.execute(
            """INSERT INTO module_impacts (matrix_id, module_name, impact_level, comment)
               SELECT ?, module_name, impact_level, comment
               FROM module_impacts WHERE matrix_id = ?""",
            (matrix_id, parent_id),
        )

    conn.commit()
    conn.close()
    return matrix_id


def get_all_matrices():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM risk_matrices ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_matrix(matrix_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM risk_matrices WHERE id = ?", (matrix_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_matrix(matrix_id):
    conn = get_db()
    conn.execute("DELETE FROM risk_matrices WHERE id = ?", (matrix_id,))
    conn.commit()
    conn.close()


# --- Impacts par module ---

def get_module_impacts(matrix_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM module_impacts WHERE matrix_id = ? ORDER BY module_name",
        (matrix_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_module_impact(matrix_id, module_name, impact_level, comment=""):
    conn = get_db()
    conn.execute(
        """INSERT INTO module_impacts (matrix_id, module_name, impact_level, comment, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(matrix_id, module_name)
           DO UPDATE SET impact_level = excluded.impact_level,
                         comment = excluded.comment,
                         updated_at = excluded.updated_at""",
        (matrix_id, module_name, impact_level, comment, datetime.now()),
    )
    conn.commit()
    conn.close()


def save_all_impacts(matrix_id, impacts_dict):
    """impacts_dict: {module_name: {"impact_level": str, "comment": str}}"""
    conn = get_db()
    for module_name, data in impacts_dict.items():
        conn.execute(
            """INSERT INTO module_impacts (matrix_id, module_name, impact_level, comment, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(matrix_id, module_name)
               DO UPDATE SET impact_level = excluded.impact_level,
                             comment = excluded.comment,
                             updated_at = excluded.updated_at""",
            (matrix_id, module_name, data.get("impact_level", "non_defini"),
             data.get("comment", ""), datetime.now()),
        )
    conn.commit()
    conn.close()
