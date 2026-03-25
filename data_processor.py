"""
Traitement des issues : extraction des modules, comptage, classement,
calcul de la frequence pour la matrice des risques ISTQB.
"""

import re
from collections import defaultdict, Counter


# Seuils ISTQB pour la probabilite (basés sur la frequence relative)
PROBABILITY_LEVELS = [
    ("tres_elevee", "Très élevée", 20),    # >= 20% des bugs
    ("elevee", "Élevée", 12),               # >= 12%
    ("moyenne", "Moyenne", 6),              # >= 6%
    ("faible", "Faible", 2),               # >= 2%
    ("tres_faible", "Très faible", 0),     # < 2%
]

IMPACT_LEVELS = {
    "critique": {"label": "Critique", "value": 4},
    "majeur": {"label": "Majeur", "value": 3},
    "modere": {"label": "Modéré", "value": 2},
    "mineur": {"label": "Mineur", "value": 1},
    "non_defini": {"label": "Non défini", "value": 0},
}

# Matrice de risque : probabilite x impact -> niveau de risque
# Valeurs: probabilite_value (1-5) * impact_value (1-4)
RISK_COLORS = {
    "critique": "#e74c3c",      # Rouge
    "eleve": "#e67e22",         # Orange
    "moyen": "#f1c40f",         # Jaune
    "faible": "#27ae60",        # Vert
    "non_evalue": "#95a5a6",    # Gris
}


def _normalize_label(label):
    return re.sub(r":{2,}", " ", label.strip()).lower().strip()


def extract_module(title):
    """Extrait le module entre crochets dans le titre."""
    match = re.match(r"\[([^\]]+)\]", title)
    if match:
        return match.group(1).strip().upper()
    return "NON CLASSÉ"


def classify_issue_type(labels):
    """Determine si l'issue est prod ou preprod."""
    for label in labels:
        normalized = _normalize_label(label)
        if "immédiat" in normalized or "immediat" in normalized:
            if "prod" in normalized:
                return "prod"
        if "urgent" in normalized and ("préprod" in normalized or "preprod" in normalized):
            return "preprod"
    return "unknown"


def process_issues(issues):
    """
    Traite les issues et retourne les donnees structurees.
    Retourne un dict avec :
    - modules_summary: {module: {prod: int, preprod: int, total: int, issues: []}}
    - total_issues: int
    - modules_ranked: [(module, total), ...] trié par total desc
    """
    modules = defaultdict(lambda: {"prod": 0, "preprod": 0, "total": 0, "issues": []})

    for issue in issues:
        module = extract_module(issue.get("title", ""))
        issue_type = classify_issue_type(issue.get("labels", []))

        if issue_type == "prod":
            modules[module]["prod"] += 1
        elif issue_type == "preprod":
            modules[module]["preprod"] += 1
        else:
            modules[module]["preprod"] += 1  # Par defaut en preprod

        modules[module]["total"] += 1
        modules[module]["issues"].append({
            "iid": issue.get("iid"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "type": issue_type,
            "created_at": issue.get("created_at", ""),
            "web_url": issue.get("web_url", ""),
        })

    total = sum(m["total"] for m in modules.values())

    # Calcul du pourcentage
    for mod_data in modules.values():
        mod_data["percentage"] = round(mod_data["total"] / total * 100, 1) if total > 0 else 0

    # Classement par total décroissant
    modules_ranked = sorted(modules.items(), key=lambda x: x[1]["total"], reverse=True)

    return {
        "modules_summary": dict(modules),
        "total_issues": total,
        "modules_ranked": modules_ranked,
    }


def get_probability_level(percentage):
    """Determine le niveau de probabilite ISTQB selon le pourcentage."""
    for key, label, threshold in PROBABILITY_LEVELS:
        if percentage >= threshold:
            return key, label
    return "tres_faible", "Très faible"


def get_probability_value(level_key):
    """Retourne la valeur numerique de la probabilite (1-5)."""
    mapping = {
        "tres_elevee": 5,
        "elevee": 4,
        "moyenne": 3,
        "faible": 2,
        "tres_faible": 1,
    }
    return mapping.get(level_key, 1)


def compute_risk_level(probability_value, impact_value):
    """Calcule le niveau de risque : probabilite x impact."""
    if impact_value == 0:
        return "non_evalue", "Non évalué", RISK_COLORS["non_evalue"]

    score = probability_value * impact_value

    if score >= 12:
        return "critique", "Critique", RISK_COLORS["critique"]
    elif score >= 8:
        return "eleve", "Élevé", RISK_COLORS["eleve"]
    elif score >= 4:
        return "moyen", "Moyen", RISK_COLORS["moyen"]
    else:
        return "faible", "Faible", RISK_COLORS["faible"]


def build_risk_matrix_data(modules_summary, module_impacts):
    """
    Construit les donnees de la matrice des risques.
    modules_summary: sortie de process_issues
    module_impacts: {module_name: impact_level_key} depuis la BDD
    """
    total = sum(m["total"] for m in modules_summary.values())
    matrix_data = []

    for module, data in sorted(modules_summary.items()):
        percentage = data.get("percentage", 0)
        prob_key, prob_label = get_probability_level(percentage)
        prob_value = get_probability_value(prob_key)

        impact_key = module_impacts.get(module, "non_defini")
        impact_info = IMPACT_LEVELS.get(impact_key, IMPACT_LEVELS["non_defini"])

        risk_key, risk_label, risk_color = compute_risk_level(prob_value, impact_info["value"])

        matrix_data.append({
            "module": module,
            "bug_count": data["total"],
            "prod_count": data["prod"],
            "preprod_count": data["preprod"],
            "percentage": percentage,
            "probability_key": prob_key,
            "probability_label": prob_label,
            "probability_value": prob_value,
            "impact_key": impact_key,
            "impact_label": impact_info["label"],
            "impact_value": impact_info["value"],
            "risk_key": risk_key,
            "risk_label": risk_label,
            "risk_color": risk_color,
        })

    # Trier par score de risque decroissant
    matrix_data.sort(key=lambda x: x["probability_value"] * x["impact_value"], reverse=True)

    return matrix_data
