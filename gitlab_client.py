"""Client API GitLab pour récupérer les issues."""

import re
import requests
from config import config


def _normalize_label(label):
    """Normaliser un label : minuscules, suppression des ::"""
    return re.sub(r":{2,}", " ", label).strip().lower()


def _match_label(label, target_keywords):
    """Vérifier si un label correspond aux mots-clés cibles."""
    normalized = _normalize_label(label)
    return all(kw in normalized for kw in target_keywords)


# Labels cibles (mots-clés à chercher, insensible casse et ::)
LABEL_PROD_KEYWORDS = ["priorit", "imm", "diat", "prod"]
LABEL_PREPROD_KEYWORDS = ["priorit", "urgent", "pr", "prod"]

# Patterns plus précis pour matcher les labels
LABEL_PROD_PATTERN = re.compile(r"priorit[ée].*imm[ée]diat.*prod", re.IGNORECASE)
LABEL_PREPROD_PATTERN = re.compile(r"priorit[ée].*urgent.*pr[ée].*prod", re.IGNORECASE)


def classify_issue_labels(labels):
    """Classifier un ticket selon ses labels. Retourne 'prod', 'preprod', ou None."""
    for label in labels:
        normalized = _normalize_label(label)
        if LABEL_PROD_PATTERN.search(normalized):
            return "prod"
        if LABEL_PREPROD_PATTERN.search(normalized):
            return "preprod"
    return None


def search_project_by_name(name):
    """Rechercher un projet GitLab par nom."""
    if config.is_mock_mode:
        return [{"id": 42, "name": "neo-fugu-pilot", "path_with_namespace": "neo-logix/legacy/neo-fugu-pilot"}]

    url = f"{config.GITLAB_URL}/api/v4/projects"
    headers = {"PRIVATE-TOKEN": config.GITLAB_TOKEN}
    params = {"search": name, "per_page": 20}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_issues(project_id=None, since="2023-01-01T00:00:00Z"):
    """Récupérer toutes les issues du projet depuis une date donnée.

    Utilise la pagination pour tout récupérer.
    """
    if config.is_mock_mode:
        from mock_data import generate_mock_issues
        return generate_mock_issues()

    pid = project_id or config.GITLAB_PROJECT_ID
    if not pid:
        return []

    url = f"{config.GITLAB_URL}/api/v4/projects/{pid}/issues"
    headers = {"PRIVATE-TOKEN": config.GITLAB_TOKEN}
    all_issues = []
    page = 1
    per_page = 100

    while True:
        params = {
            "per_page": per_page,
            "page": page,
            "created_after": since,
            "scope": "all",
            "state": "all",  # opened + closed
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        issues = response.json()
        if not issues:
            break
        all_issues.extend(issues)
        page += 1

    return all_issues


def filter_bug_issues(issues):
    """Filtrer les issues qui sont des bugs prod ou préprod."""
    filtered = []
    for issue in issues:
        labels = issue.get("labels", [])
        category = classify_issue_labels(labels)
        if category:
            issue["_bug_category"] = category
            filtered.append(issue)
    return filtered
