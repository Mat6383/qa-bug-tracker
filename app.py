"""
QA Bug Tracker & Matrice des Risques ISTQB
Application Flask principale.
"""

import json
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from config import Config
from database import (
    init_db, create_matrix, get_all_matrices, get_matrix,
    delete_matrix, get_module_impacts, save_all_impacts,
)
from gitlab_client import fetch_all_bug_issues, search_projects
from data_processor import (
    process_issues, build_risk_matrix_data, IMPACT_LEVELS,
)
from excel_export import export_risk_matrix_to_excel

app = Flask(__name__)

# Cache simple en memoire pour les donnees issues
_issues_cache = {"data": None, "timestamp": None}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_processed_data(force_refresh=False):
    """Recupere et traite les issues, avec cache."""
    now = datetime.now()
    if (
        not force_refresh
        and _issues_cache["data"]
        and _issues_cache["timestamp"]
        and (now - _issues_cache["timestamp"]).seconds < CACHE_TTL_SECONDS
    ):
        return _issues_cache["data"]

    issues = fetch_all_bug_issues()
    processed = process_issues(issues)
    _issues_cache["data"] = processed
    _issues_cache["timestamp"] = now
    return processed


# --- Pages ---

@app.route("/")
def dashboard():
    return render_template("dashboard.html", gitlab_configured=Config.is_gitlab_configured())


@app.route("/risk-matrix")
def risk_matrix():
    matrices = get_all_matrices()
    return render_template(
        "risk_matrix.html",
        matrices=matrices,
        impact_levels=IMPACT_LEVELS,
        gitlab_configured=Config.is_gitlab_configured(),
    )


# --- API endpoints ---

@app.route("/api/bugs-data")
def api_bugs_data():
    """Retourne les donnees de bugs pour les graphiques."""
    try:
        force = request.args.get("refresh", "false") == "true"
        data = _get_processed_data(force_refresh=force)

        modules = []
        for module, stats in data["modules_ranked"]:
            modules.append({
                "module": module,
                "prod": stats["prod"],
                "preprod": stats["preprod"],
                "total": stats["total"],
                "percentage": stats["percentage"],
            })

        return jsonify({
            "success": True,
            "total_issues": data["total_issues"],
            "modules": modules,
            "mock_mode": not Config.is_gitlab_configured(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/search-projects")
def api_search_projects():
    """Recherche de projets GitLab."""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"success": True, "projects": []})
    try:
        projects = search_projects(query)
        return jsonify({
            "success": True,
            "projects": [
                {"id": p["id"], "name": p.get("name", ""), "path": p.get("path_with_namespace", "")}
                for p in projects
            ],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/matrix/create", methods=["POST"])
def api_create_matrix():
    """Cree une nouvelle matrice des risques."""
    body = request.json
    version = body.get("version", "").strip()
    description = body.get("description", "").strip()
    parent_id = body.get("parent_id")

    if not version:
        return jsonify({"success": False, "error": "La version est obligatoire."}), 400

    try:
        # Si pas de parent mais qu'il existe des matrices, prendre la plus recente
        if not parent_id:
            existing = get_all_matrices()
            if existing:
                parent_id = existing[0]["id"]

        matrix_id = create_matrix(version, description, parent_id)

        # Ajouter les modules connus depuis les donnees de bugs
        data = _get_processed_data()
        existing_impacts = {m["module_name"]: m for m in get_module_impacts(matrix_id)}

        new_impacts = {}
        for module in data["modules_summary"]:
            if module not in existing_impacts:
                new_impacts[module] = {"impact_level": "non_defini", "comment": ""}

        if new_impacts:
            save_all_impacts(matrix_id, new_impacts)

        return jsonify({"success": True, "matrix_id": matrix_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/matrix/<int:matrix_id>")
def api_get_matrix(matrix_id):
    """Retourne les donnees d'une matrice."""
    matrix = get_matrix(matrix_id)
    if not matrix:
        return jsonify({"success": False, "error": "Matrice introuvable."}), 404

    try:
        data = _get_processed_data()
        impacts = get_module_impacts(matrix_id)
        impacts_dict = {m["module_name"]: m["impact_level"] for m in impacts}
        comments_dict = {m["module_name"]: m.get("comment", "") for m in impacts}

        risk_data = build_risk_matrix_data(data["modules_summary"], impacts_dict)

        # Ajouter les commentaires
        for item in risk_data:
            item["comment"] = comments_dict.get(item["module"], "")

        return jsonify({
            "success": True,
            "matrix": matrix,
            "risk_data": risk_data,
            "impact_levels": {k: v["label"] for k, v in IMPACT_LEVELS.items()},
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/matrix/<int:matrix_id>/save", methods=["POST"])
def api_save_matrix(matrix_id):
    """Sauvegarde les impacts d'une matrice."""
    body = request.json
    impacts = body.get("impacts", {})

    try:
        formatted = {}
        for module, data in impacts.items():
            formatted[module] = {
                "impact_level": data.get("impact_level", "non_defini"),
                "comment": data.get("comment", ""),
            }
        save_all_impacts(matrix_id, formatted)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/matrix/<int:matrix_id>/delete", methods=["POST"])
def api_delete_matrix(matrix_id):
    """Supprime une matrice."""
    try:
        delete_matrix(matrix_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/matrix/<int:matrix_id>/export")
def api_export_matrix(matrix_id):
    """Exporte la matrice en Excel."""
    matrix = get_matrix(matrix_id)
    if not matrix:
        return jsonify({"success": False, "error": "Matrice introuvable."}), 404

    try:
        data = _get_processed_data()
        impacts = get_module_impacts(matrix_id)
        impacts_dict = {m["module_name"]: m["impact_level"] for m in impacts}
        risk_data = build_risk_matrix_data(data["modules_summary"], impacts_dict)

        buffer = export_risk_matrix_to_excel(matrix, risk_data)

        filename = f"matrice_risques_{matrix['version'].replace(' ', '_')}.xlsx"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    print(f"\n{'='*60}")
    print(f"  QA Bug Tracker - Matrice des Risques ISTQB")
    print(f"  Mode: {'DEMO (données simulées)' if not Config.is_gitlab_configured() else 'GitLab connecté'}")
    print(f"  URL: http://{Config.APP_HOST}:{Config.APP_PORT}")
    print(f"{'='*60}\n")
    app.run(
        host=Config.APP_HOST,
        port=Config.APP_PORT,
        debug=Config.APP_MODE == "local",
    )
