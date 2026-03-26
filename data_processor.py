"""
Traitement des issues : extraction modules, comptage, probabilite ISTQB.
"""

import re
from collections import defaultdict


# ─── Niveaux ISTQB ────────────────────────────────────────────────────────────

# (key, label, value_numerique, seuil_pourcentage)
PROBABILITY_LEVELS = [
    ("tres_elevee", "Très élevée", 5, 20),
    ("elevee",      "Élevée",      4, 12),
    ("moyenne",     "Moyenne",     3,  6),
    ("faible",      "Faible",      2,  2),
    ("tres_faible", "Très faible", 1,  0),
]

# Liste ordonnée pour les selects HTML
IMPACT_LEVELS = [
    {"key": "critique",   "label": "Critique",   "value": 4},
    {"key": "majeur",     "label": "Majeur",      "value": 3},
    {"key": "modere",     "label": "Modéré",      "value": 2},
    {"key": "mineur",     "label": "Mineur",      "value": 1},
    {"key": "non_defini", "label": "Non défini",  "value": 0},
]

# Dict pour accès rapide
IMPACT_DICT = {il["key"]: il for il in IMPACT_LEVELS}

RISK_COLORS = {
    "critique":   "#e74c3c",
    "eleve":      "#e67e22",
    "moyen":      "#f1c40f",
    "faible":     "#27ae60",
    "non_evalue": "#95a5a6",
}


# ─── Extraction titre ─────────────────────────────────────────────────────────

def extract_all_modules(title):
    """Retourne tous les modules [X][Y] en début de titre."""
    matches = re.findall(r'\[([^\]]+)\]', title)
    return [m.strip().upper() for m in matches] if matches else ["NON CLASSÉ"]


def extract_fonctionnalite(title):
    """Retourne la description après les [MODULE] du titre."""
    result = re.sub(r'^(\s*\[[^\]]+\]\s*)+', '', title).strip()
    return result if result else title


def _normalize_label(label):
    return re.sub(r":{2,}", " ", label.strip()).lower().strip()


def classify_issue_type(labels):
    """Détermine si l'issue est prod ou préprod."""
    for label in labels:
        norm = _normalize_label(label)
        if ("immédiat" in norm or "immediat" in norm) and "prod" in norm:
            return "prod"
        if "urgent" in norm and ("préprod" in norm or "preprod" in norm):
            return "preprod"
    return "preprod"


# ─── Traitement issues ────────────────────────────────────────────────────────

def process_issues(issues, year=None):
    """
    Traite les issues GitLab.
    - year : filtre optionnel (int ou str)
    Retourne un dict avec total, total_prod, total_preprod, modules, modules_ranked.
    """
    if year:
        year_str = str(year)
        issues = [i for i in issues if i.get("created_at", "")[:4] == year_str]

    modules = defaultdict(lambda: {"prod": 0, "preprod": 0, "total": 0})

    for issue in issues:
        title = issue.get("title", "")
        all_mods = extract_all_modules(title)
        itype = classify_issue_type(issue.get("labels", []))

        for mod in all_mods:
            if itype == "prod":
                modules[mod]["prod"] += 1
            else:
                modules[mod]["preprod"] += 1
            modules[mod]["total"] += 1

    grand_total = sum(m["total"] for m in modules.values())

    for mod_data in modules.values():
        mod_data["percentage"] = (
            round(mod_data["total"] / grand_total * 100, 1) if grand_total > 0 else 0
        )

    modules_ranked = sorted(modules.items(), key=lambda x: x[1]["total"], reverse=True)
    total_prod = sum(m["prod"] for m in modules.values())
    total_preprod = sum(m["preprod"] for m in modules.values())

    return {
        "modules":        dict(modules),
        "modules_ranked": modules_ranked,
        "total":          grand_total,
        "total_prod":     total_prod,
        "total_preprod":  total_preprod,
    }


# ─── Calculs risque ───────────────────────────────────────────────────────────

def get_probability(module_field, modules_data):
    """
    Calcule la probabilité pour un champ module (peut être "EDI, ARTICLE").
    Prend le module ayant le plus de bugs.
    """
    mod_list = [m.strip() for m in module_field.split(",")]
    best_pct = max(
        (modules_data[m]["percentage"] for m in mod_list if m in modules_data),
        default=0
    )
    for key, label, value, threshold in PROBABILITY_LEVELS:
        if best_pct >= threshold:
            return {"key": key, "label": label, "value": value}
    return {"key": "tres_faible", "label": "Très faible", "value": 1}


def compute_risk(prob_value, impact_value):
    """Retourne le niveau de risque ISTQB (clé, label, couleur)."""
    if impact_value == 0:
        return {"key": "non_evalue", "label": "Non évalué", "color": RISK_COLORS["non_evalue"]}

    score = prob_value * impact_value

    if score >= 12:
        return {"key": "critique", "label": "Critique", "color": RISK_COLORS["critique"]}
    elif score >= 8:
        return {"key": "eleve",    "label": "Élevé",    "color": RISK_COLORS["eleve"]}
    elif score >= 4:
        return {"key": "moyen",    "label": "Moyen",    "color": RISK_COLORS["moyen"]}
    else:
        return {"key": "faible",   "label": "Faible",   "color": RISK_COLORS["faible"]}


def enrich_row(row, modules_data):
    """
    Enrichit une ligne de matrice avec probabilité, impact et risque calculés.
    row : dict depuis la BDD (module, fonctionnalite, gitlab_iid, impact_level, ...)
    """
    prob = get_probability(row.get("module", ""), modules_data)
    impact_key = row.get("impact_level", "non_defini")
    impact = IMPACT_DICT.get(impact_key, IMPACT_DICT["non_defini"])
    risk = compute_risk(prob["value"], impact["value"])

    return {
        **row,
        "probability":  prob,
        "impact":       impact,
        "risk_label":   risk["label"],
        "risk_color":   risk["color"],
        "risk_key":     risk["key"],
    }
