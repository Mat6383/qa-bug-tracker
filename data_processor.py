"""Traitement des données : extraction des modules, comptage, classification."""

import re
import csv
import io
from collections import Counter
from gitlab_client import classify_issue_labels


# ─── Niveaux ISTQB ──────────────────────────────────────────────

PROBABILITY_LEVELS = [
    {"key": "tres_faible", "label": "Très faible", "value": 1},
    {"key": "faible", "label": "Faible", "value": 2},
    {"key": "moyenne", "label": "Moyenne", "value": 3},
    {"key": "elevee", "label": "Élevée", "value": 4},
    {"key": "tres_elevee", "label": "Très élevée", "value": 5},
]

IMPACT_LEVELS = [
    {"key": "non_defini", "label": "Non défini", "value": 0},
    {"key": "mineur", "label": "Mineur", "value": 1},
    {"key": "modere", "label": "Modéré", "value": 2},
    {"key": "majeur", "label": "Majeur", "value": 3},
    {"key": "critique", "label": "Critique", "value": 4},
]

# Matrice de risque : probabilité (ligne) × impact (colonne)
# Valeurs : 1=Faible, 2=Modéré, 3=Élevé, 4=Critique
RISK_MATRIX = {
    1: {1: 1, 2: 1, 3: 2, 4: 2},  # Très faible
    2: {1: 1, 2: 2, 3: 2, 4: 3},  # Faible
    3: {1: 2, 2: 2, 3: 3, 4: 3},  # Moyenne
    4: {1: 2, 2: 3, 3: 3, 4: 4},  # Élevée
    5: {1: 3, 2: 3, 3: 4, 4: 4},  # Très élevée
}

RISK_LABELS = {
    0: {"label": "Non défini", "color": "#9e9e9e"},
    1: {"label": "Faible", "color": "#4caf50"},
    2: {"label": "Modéré", "color": "#ff9800"},
    3: {"label": "Élevé", "color": "#f44336"},
    4: {"label": "Critique", "color": "#b71c1c"},
}


def compute_risk(probability_value, impact_value):
    """Calculer le niveau de risque à partir de la probabilité et de l'impact."""
    if impact_value == 0 or probability_value == 0:
        return 0, RISK_LABELS[0]
    risk_value = RISK_MATRIX.get(probability_value, {}).get(impact_value, 0)
    return risk_value, RISK_LABELS.get(risk_value, RISK_LABELS[0])


# ─── Extraction des modules depuis les titres ────────────────────

def extract_modules(title):
    """Extraire tous les modules entre [] d'un titre.

    Exemples:
        "[ARTICLE] blabla" → ["ARTICLE"]
        "[EDI][STOCK] blabla" → ["EDI", "STOCK"]
        "Pas de module" → ["NON CLASSÉ"]
    """
    modules = re.findall(r'\[([^\]]+)\]', title)
    if modules:
        return [m.strip().upper() for m in modules]
    return ["NON CLASSÉ"]


def extract_fonctionnalite(title):
    """Extraire la partie fonctionnalité (après les []) d'un titre.

    Exemple: "[EDI][STOCK] Ajout des valeurs" → "Ajout des valeurs"
    """
    cleaned = re.sub(r'\[[^\]]*\]\s*', '', title).strip()
    return cleaned if cleaned else title


# ─── Traitement des issues ───────────────────────────────────────

def process_issues(issues, year=None):
    """Traiter les issues et produire les statistiques par module.

    Args:
        issues: Liste des issues (filtrées bugs uniquement)
        year: Année de filtrage (None = toutes les années)

    Returns:
        dict avec modules_summary, total_prod, total_preprod, etc.
    """
    # Filtrage par année
    if year:
        year = int(year)
        issues = [
            i for i in issues
            if i.get("created_at", "").startswith(str(year))
        ]

    # Comptage par module
    prod_counter = Counter()
    preprod_counter = Counter()

    for issue in issues:
        category = issue.get("_bug_category")
        if not category:
            category = classify_issue_labels(issue.get("labels", []))
        if not category:
            continue

        modules = extract_modules(issue.get("title", ""))
        counter = prod_counter if category == "prod" else preprod_counter
        for module in modules:
            counter[module] += 1

    # Fusionner tous les modules
    all_modules = sorted(set(list(prod_counter.keys()) + list(preprod_counter.keys())))

    total_prod = sum(prod_counter.values())
    total_preprod = sum(preprod_counter.values())
    total = total_prod + total_preprod

    modules_summary = []
    for module in all_modules:
        prod = prod_counter.get(module, 0)
        preprod = preprod_counter.get(module, 0)
        mod_total = prod + preprod
        percentage = round(mod_total / total * 100, 1) if total > 0 else 0
        modules_summary.append({
            "module": module,
            "prod": prod,
            "preprod": preprod,
            "total": mod_total,
            "percentage": percentage,
        })

    # Trier par total décroissant
    modules_summary.sort(key=lambda x: x["total"], reverse=True)

    return {
        "modules_summary": modules_summary,
        "total_prod": total_prod,
        "total_preprod": total_preprod,
        "total": total,
        "year": year,
    }


def get_module_bug_counts(issues):
    """Obtenir un dictionnaire module → nombre total de bugs (toutes années)."""
    counter = Counter()
    for issue in issues:
        modules = extract_modules(issue.get("title", ""))
        for module in modules:
            counter[module] += 1
    return dict(counter)


def compute_probability_level(module, module_bug_counts):
    """Calculer le niveau de probabilité d'un module basé sur la fréquence des bugs.

    Seuils basés sur les percentiles de la distribution.
    """
    if not module_bug_counts:
        return PROBABILITY_LEVELS[0]  # Très faible

    counts = sorted(module_bug_counts.values())
    max_count = max(counts) if counts else 1

    # Pour les multi-modules, prendre le max
    modules = [m.strip() for m in module.split(",")]
    module_count = max(module_bug_counts.get(m.strip().upper(), 0) for m in modules)

    if max_count == 0:
        return PROBABILITY_LEVELS[0]

    # Ratio par rapport au module le plus bugué
    ratio = module_count / max_count

    if ratio >= 0.8:
        return PROBABILITY_LEVELS[4]  # Très élevée
    elif ratio >= 0.6:
        return PROBABILITY_LEVELS[3]  # Élevée
    elif ratio >= 0.4:
        return PROBABILITY_LEVELS[2]  # Moyenne
    elif ratio >= 0.2:
        return PROBABILITY_LEVELS[1]  # Faible
    else:
        return PROBABILITY_LEVELS[0]  # Très faible


# ─── Import CSV ──────────────────────────────────────────────────

def parse_gitlab_csv(csv_content):
    """Parser un fichier CSV exporté de GitLab.

    Retourne une liste de dicts avec: modules, fonctionnalite, gitlab_iid, labels.
    """
    # Essayer différents encodages
    if isinstance(csv_content, bytes):
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                csv_content = csv_content.decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue

    reader = csv.DictReader(io.StringIO(csv_content))

    # Mapper les noms de colonnes (flexibilité)
    rows = []
    for row in reader:
        title = row.get("Title", row.get("title", row.get("Titre", "")))
        issue_id = row.get("Issue ID", row.get("issue_id", row.get("Id", "")))
        labels_str = row.get("Labels", row.get("labels", ""))

        if not title:
            continue

        modules = extract_modules(title)
        fonctionnalite = extract_fonctionnalite(title)

        # Vérifier si c'est un bug prod ou préprod via les labels
        labels = [l.strip() for l in labels_str.split(",")]
        category = classify_issue_labels(labels)

        rows.append({
            "modules": modules,
            "module_display": ", ".join(modules),
            "fonctionnalite": fonctionnalite,
            "gitlab_iid": str(issue_id).strip(),
            "labels": labels,
            "category": category,
            "title": title,
        })

    return rows
