"""Gestion de la base de données SQLite."""

import sqlite3
import json
from datetime import datetime
from config import config


def get_db():
    """Obtenir une connexion à la base de données."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialiser la base de données."""
    conn = get_db()
    cursor = conn.cursor()

    # Table des matrices de risques
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_matrices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES risk_matrices(id)
        )
    """)

    # Table des lignes de détail de la matrice
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matrix_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matrix_id INTEGER NOT NULL,
            module TEXT NOT NULL,
            fonctionnalite TEXT DEFAULT '',
            gitlab_iid TEXT DEFAULT '',
            probability_level TEXT DEFAULT 'non_defini',
            impact_level TEXT DEFAULT 'non_defini',
            is_manual INTEGER DEFAULT 0,
            FOREIGN KEY (matrix_id) REFERENCES risk_matrices(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ─── Matrices CRUD ───────────────────────────────────────────────

def create_matrix(name, version, parent_id=None):
    """Créer une nouvelle matrice de risques."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO risk_matrices (name, version, created_at, updated_at, parent_id) VALUES (?, ?, ?, ?, ?)",
        (name, version, now, now, parent_id)
    )
    matrix_id = cursor.lastrowid

    # Si parent_id, hériter des lignes de la matrice parente
    if parent_id:
        parent_rows = get_matrix_rows(parent_id)
        for row in parent_rows:
            cursor.execute(
                """INSERT INTO matrix_rows
                   (matrix_id, module, fonctionnalite, gitlab_iid, probability_level, impact_level, is_manual)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (matrix_id, row["module"], row["fonctionnalite"], row["gitlab_iid"],
                 row["probability_level"], row["impact_level"], row["is_manual"])
            )

    conn.commit()
    conn.close()
    return matrix_id


def get_all_matrices():
    """Récupérer toutes les matrices."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM risk_matrices ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_matrix(matrix_id):
    """Récupérer une matrice par son ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM risk_matrices WHERE id = ?", (matrix_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_matrix(matrix_id):
    """Supprimer une matrice."""
    conn = get_db()
    conn.execute("DELETE FROM risk_matrices WHERE id = ?", (matrix_id,))
    conn.commit()
    conn.close()


# ─── Lignes de matrice CRUD ──────────────────────────────────────

def get_matrix_rows(matrix_id):
    """Récupérer toutes les lignes d'une matrice."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM matrix_rows WHERE matrix_id = ? ORDER BY module, id",
        (matrix_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_matrix_row(matrix_id, module, fonctionnalite="", gitlab_iid="",
                   probability_level="non_defini", impact_level="non_defini", is_manual=0):
    """Ajouter une ligne à une matrice."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO matrix_rows
           (matrix_id, module, fonctionnalite, gitlab_iid, probability_level, impact_level, is_manual)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (matrix_id, module, fonctionnalite, gitlab_iid, probability_level, impact_level, is_manual)
    )
    row_id = cursor.lastrowid
    # Mettre à jour la date de modification de la matrice
    conn.execute(
        "UPDATE risk_matrices SET updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), matrix_id)
    )
    conn.commit()
    conn.close()
    return row_id


def update_matrix_row(row_id, **kwargs):
    """Mettre à jour une ligne de matrice."""
    conn = get_db()
    allowed = {"module", "fonctionnalite", "gitlab_iid", "probability_level", "impact_level"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        conn.close()
        return

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [row_id]
    conn.execute(f"UPDATE matrix_rows SET {set_clause} WHERE id = ?", values)

    # Mettre à jour la date de modification de la matrice parente
    row = conn.execute("SELECT matrix_id FROM matrix_rows WHERE id = ?", (row_id,)).fetchone()
    if row:
        conn.execute(
            "UPDATE risk_matrices SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), row["matrix_id"])
        )

    conn.commit()
    conn.close()


def delete_matrix_row(row_id):
    """Supprimer une ligne de matrice."""
    conn = get_db()
    conn.execute("DELETE FROM matrix_rows WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
