"""
Client API GitLab : recuperation des issues par label.
Bascule automatiquement en mode mock si pas de token configure.
"""

import re
import requests
from config import Config
from mock_data import generate_mock_issues


def _normalize_label(label):
    """Normalise un label : minuscule, suppression des ::"""
    return re.sub(r":{2,}", " ", label.strip()).lower().strip()


def _label_matches(issue_label, target_label):
    """Comparaison flexible de labels (insensible casse et ::)."""
    return _normalize_label(issue_label) == _normalize_label(target_label)


def _fetch_issues_by_label(project_id, label, created_after):
    """Recupere toutes les issues paginées pour un label donné via l'API GitLab."""
    url = f"{Config.GITLAB_URL.rstrip('/')}/api/v4/projects/{project_id}/issues"
    headers = {"PRIVATE-TOKEN": Config.GITLAB_TOKEN}
    all_issues = []
    page = 1
    per_page = 100

    while True:
        params = {
            "labels": label,
            "created_after": created_after,
            "per_page": per_page,
            "page": page,
            "state": "all",
            "scope": "all",
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        issues = response.json()

        if not issues:
            break

        all_issues.extend(issues)
        page += 1

        # Verifier s'il y a une page suivante
        if len(issues) < per_page:
            break

    return all_issues


def search_projects(query):
    """Recherche de projets GitLab par nom."""
    if not Config.is_gitlab_configured():
        return [
            {"id": 42, "name": "ERP Demo Project", "path_with_namespace": "demo/erp-project"},
            {"id": 99, "name": "ERP Module Test", "path_with_namespace": "demo/erp-module-test"},
        ]

    url = f"{Config.GITLAB_URL.rstrip('/')}/api/v4/projects"
    headers = {"PRIVATE-TOKEN": Config.GITLAB_TOKEN}
    params = {"search": query, "per_page": 20, "order_by": "name"}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_all_bug_issues(project_id=None):
    """
    Recupere toutes les issues bugs (prod + preprod) depuis 2023-01-01.
    Retourne en mode mock si GitLab n'est pas configure.
    """
    if not Config.is_gitlab_configured():
        return generate_mock_issues()

    pid = project_id or Config.GITLAB_PROJECT_ID
    if not pid:
        raise ValueError("Aucun Project ID configuré. Renseignez GITLAB_PROJECT_ID dans .env ou sélectionnez un projet.")

    created_after = Config.DATA_START_DATE + "T00:00:00Z"

    # Recuperer les issues pour les deux labels
    # On essaie d'abord avec le format exact, l'API GitLab gere la casse
    prod_issues = _fetch_issues_by_label(pid, "Priorité::Immédiat prod", created_after)
    preprod_issues = _fetch_issues_by_label(pid, "Priorité::Urgent préprod", created_after)

    # Dedoublonner par ID (un ticket pourrait avoir les deux labels)
    seen_ids = set()
    all_issues = []
    for issue in prod_issues + preprod_issues:
        if issue["id"] not in seen_ids:
            seen_ids.add(issue["id"])
            all_issues.append(issue)

    return all_issues
