"""
QA Bug Tracker & Matrice des Risques ISTQB — Application Flask principale.
"""

import io
import csv
import chardet
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

from config import Config
from database import (
    init_db,
    get_all_matrices, create_matrix, get_matrix, delete_matrix,
    get_matrix_rows, add_matrix_row, update_row_impact, delete_row,
)
from gitlab_client import fetch_all_bug_issues, search_projects
from data_processor import process_issues, enrich_row, IMPACT_LEVELS
from excel_export import export_risk_matrix_to_excel

app = Flask(__name__)

# ─── Cache brut (issues non filtrées) ────────────────────────────────────────
_raw_cache = {"data": None, "timestamp": None}
CACHE_TTL = 300  # 5 minutes


def _get_raw_issues(force=False):
    now = datetime.now()
    if (
        not force
        and _raw_cache["data"] is not None
        and _raw_cache["timestamp"]
        and (now - _raw_cache["timestamp"]).seconds < CACHE_TTL
    ):
        return _raw_cache["data"]

    issues = fetch_all_bug_issues()
    _raw_cache["data"] = issues
    _raw_cache["timestamp"] = now
    return issues


def _processed(year=None):
    return process_issues(_get_raw_issues(), year=year)


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        current_year=datetime.now().year,
        is_mock=not Config.is_gitlab_configured(),
    )


@app.route("/risk-matrix")
def risk_matrix():
    return render_template(
        "risk_matrix.html",
        impact_levels=IMPACT_LEVELS,
        is_mock=not Config.is_gitlab_configured(),
    )


# ─── API Dashboard ────────────────────────────────────────────────────────────

@app.route("/api/bugs-data")
def api_bugs_data():
    """Données pour le dashboard (graphiques + tableau), filtrables par année."""
    try:
        year_param = request.args.get("year")
        year = int(year_param) if year_param else None
        data = _processed(year=year)

        modules_summary = [
            {
                "module":     mod,
                "prod":       stats["prod"],
                "preprod":    stats["preprod"],
                "total":      stats["total"],
                "percentage": stats["percentage"],
            }
            for mod, stats in data["modules_ranked"]
        ]

        return jsonify({
            "total":           data["total"],
            "total_prod":      data["total_prod"],
            "total_preprod":   data["total_preprod"],
            "modules_summary": modules_summary,
            "year":            year,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh-cache", methods=["POST"])
def api_refresh_cache():
    """Force le rechargement des données depuis GitLab."""
    try:
        _get_raw_issues(force=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search-projects")
def api_search_projects():
    """Recherche de projets GitLab par nom."""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"projects": []})
    try:
        projects = search_projects(query)
        return jsonify({
            "projects": [
                {"id": p["id"], "name": p.get("name", ""), "path": p.get("path_with_namespace", "")}
                for p in projects
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API Matrices ─────────────────────────────────────────────────────────────

@app.route("/api/matrices", methods=["GET"])
def api_list_matrices():
    return jsonify(get_all_matrices())


@app.route("/api/matrices", methods=["POST"])
def api_create_matrix():
    body = request.json or {}
    name = body.get("name", "").strip()
    version = body.get("version", "").strip()
    parent_id = body.get("parent_id")

    if not name or not version:
        return jsonify({"error": "Nom et version sont requis."}), 400

    # Si pas de parent explicite → hériter de la plus récente automatiquement
    if not parent_id:
        existing = get_all_matrices()
        if existing:
            parent_id = existing[0]["id"]

    mid = create_matrix(name, version, parent_id)
    return jsonify({"id": mid}), 201


@app.route("/api/matrices/<int:matrix_id>", methods=["GET"])
def api_get_matrix(matrix_id):
    matrix = get_matrix(matrix_id)
    if not matrix:
        return jsonify({"error": "Matrice introuvable."}), 404

    raw_data = _processed()
    modules_data = raw_data["modules"]
    rows = [enrich_row(r, modules_data) for r in get_matrix_rows(matrix_id)]

    return jsonify({"matrix": matrix, "rows": rows})


@app.route("/api/matrices/<int:matrix_id>", methods=["DELETE"])
def api_delete_matrix(matrix_id):
    delete_matrix(matrix_id)
    return jsonify({"success": True})


# ─── API Lignes ───────────────────────────────────────────────────────────────

@app.route("/api/matrices/<int:matrix_id>/rows", methods=["POST"])
def api_add_row(matrix_id):
    body = request.json or {}
    module = body.get("module", "").strip()
    if not module:
        return jsonify({"error": "Le module est requis."}), 400

    weight_raw = body.get("weight")
    weight = int(weight_raw) if weight_raw not in (None, "", "null") else None

    row_id = add_matrix_row(
        matrix_id,
        module=module,
        fonctionnalite=body.get("fonctionnalite", "").strip(),
        gitlab_iid=str(body.get("gitlab_iid", "")).strip(),
        impact_level=body.get("impact_level", "non_defini"),
        weight=weight,
        impact_description=body.get("impact_description", "").strip(),
    )
    return jsonify({"id": row_id}), 201


@app.route("/api/matrix-rows/<int:row_id>", methods=["PUT"])
def api_update_row(row_id):
    body = request.json or {}
    impact_level = body.get("impact_level", "non_defini")
    update_row_impact(row_id, impact_level)
    return jsonify({"success": True})


@app.route("/api/matrix-rows/<int:row_id>", methods=["DELETE"])
def api_delete_row(row_id):
    delete_row(row_id)
    return jsonify({"success": True})


# ─── Import CSV ───────────────────────────────────────────────────────────────

def _extract_impact_from_text(text):
    """
    Cherche une section [Impact] (insensible à la casse) dans un texte markdown.
    Retourne le contenu trouvé, ou '' si absent.
    Formats supportés : [impact], ## impact, **impact**, # impact
    """
    import re
    if not text:
        return ""
    # Pattern : ligne contenant [impact] ou ## impact ou **impact** suivie du contenu
    pattern = re.compile(
        r'(?:^|\n)\s*(?:\[impact\]|#{1,3}\s*impact|\*{1,2}impact\*{1,2})'
        r'[^\n]*\n(.*?)(?=\n\s*(?:\[|\#|\*{1,2}\w|\Z))',
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()[:500]  # max 500 chars
    # Fallback : cherche simplement "impact" suivi de ":" sur la même ligne
    simple = re.search(r'impact\s*[:：]\s*(.+)', text, re.IGNORECASE)
    if simple:
        return simple.group(1).strip()[:500]
    return ""


def _find_column(headers, candidates):
    """Trouve la première colonne correspondant à l'une des variantes."""
    headers_lower = [h.lower().strip() for h in headers]
    for candidate in candidates:
        if candidate.lower() in headers_lower:
            return headers_lower.index(candidate.lower())
    return None


@app.route("/api/matrices/<int:matrix_id>/import-csv", methods=["POST"])
def api_import_csv(matrix_id):
    if "file" not in request.files:
        return jsonify({"error": "Fichier manquant."}), 400

    file = request.files["file"]
    raw = file.read()

    # Détection encodage
    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"
    try:
        content = raw.decode(encoding)
    except Exception:
        content = raw.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []

    # Détection flexible des colonnes
    title_idx   = _find_column(headers, ["Title", "title", "Titre", "titre"])
    iid_idx     = _find_column(headers, ["Issue ID", "issue_id", "IID", "iid", "ID", "id"])
    weight_idx  = _find_column(headers, ["Weight", "weight", "Poids", "poids"])
    desc_idx    = _find_column(headers, ["Description", "description"])

    if title_idx is None:
        return jsonify({"error": "Colonne 'Title' introuvable dans le CSV."}), 400

    # Données de fréquence pour la probabilité
    raw_data = _processed()
    modules_data = raw_data["modules"]

    count = 0
    for row in reader:
        row_values = list(row.values())
        title = row_values[title_idx].strip() if title_idx < len(row_values) else ""
        if not title:
            continue

        gitlab_iid = ""
        if iid_idx is not None and iid_idx < len(row_values):
            gitlab_iid = str(row_values[iid_idx]).strip()

        # Poids
        weight = None
        if weight_idx is not None and weight_idx < len(row_values):
            w = row_values[weight_idx].strip()
            try:
                weight = int(w) if w else None
            except ValueError:
                weight = None

        # Impact : chercher [impact] dans la description (insensible à la casse)
        impact_description = ""
        if desc_idx is not None and desc_idx < len(row_values):
            desc = row_values[desc_idx]
            impact_description = _extract_impact_from_text(desc)

        # Extraction modules et fonctionnalité depuis le titre
        from data_processor import extract_all_modules, extract_fonctionnalite
        all_mods = extract_all_modules(title)
        module_field = ", ".join(all_mods)
        fonctionnalite = extract_fonctionnalite(title)

        add_matrix_row(
            matrix_id,
            module=module_field,
            fonctionnalite=fonctionnalite,
            gitlab_iid=gitlab_iid,
            impact_level="non_defini",
            weight=weight,
            impact_description=impact_description,
        )
        count += 1

    return jsonify({"count": count})


# ─── Export Excel ─────────────────────────────────────────────────────────────

@app.route("/api/matrices/<int:matrix_id>/export-excel")
def api_export_excel(matrix_id):
    matrix = get_matrix(matrix_id)
    if not matrix:
        return jsonify({"error": "Matrice introuvable."}), 404

    raw_data = _processed()
    rows = [enrich_row(r, raw_data["modules"]) for r in get_matrix_rows(matrix_id)]

    buffer = export_risk_matrix_to_excel(matrix, rows)
    filename = f"matrice_risques_{matrix['version'].replace(' ', '_')}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─── Lancement ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print(f"\n{'='*60}")
    print(f"  QA Bug Tracker — Matrice des Risques ISTQB")
    print(f"  Mode : {'DEMO (données simulées)' if not Config.is_gitlab_configured() else 'GitLab connecté'}")
    print(f"  URL  : http://{Config.APP_HOST}:{Config.APP_PORT}")
    print(f"{'='*60}\n")
    app.run(
        host=Config.APP_HOST,
        port=Config.APP_PORT,
        debug=Config.APP_MODE == "local",
        use_reloader=False,
    )
