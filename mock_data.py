"""
Donnees simulees pour le mode demo (pas de token GitLab).
Simule des issues GitLab avec des modules ERP varies.
"""

import random
from datetime import datetime, timedelta

MODULES = [
    "ARTICLE", "COMMANDE", "FACTURATION", "STOCK", "CLIENT",
    "FOURNISSEUR", "COMPTABILITE", "LIVRAISON", "PRODUCTION",
    "TABLEAU DE BORD", "UTILISATEUR", "PARAMETRAGE", "REPORTING",
    "IMPORT/EXPORT", "WORKFLOW",
]

PROD_LABEL = "priorité::immédiat prod"
PREPROD_LABEL = "priorité::urgent préprod"

TITRES_SUFFIXES = [
    "Impossible de sauvegarder",
    "Erreur 500 au chargement",
    "Données incorrectes après import",
    "Bouton inactif sur la page principale",
    "Calcul de TVA erroné",
    "Doublon créé automatiquement",
    "Champ obligatoire non vérifié",
    "Export PDF vide",
    "Timeout lors de la recherche",
    "Affichage incorrect des dates",
    "Perte de données après modification",
    "Filtre ne fonctionne pas",
    "Droits d'accès non respectés",
    "Notification non envoyée",
    "Incohérence entre liste et détail",
    "Crash lors de la suppression",
    "Pagination cassée",
    "Tri alphabétique inversé",
    "Caractères spéciaux non supportés",
    "Performance dégradée sur gros volume",
]


def _random_date():
    start = datetime(2023, 1, 1)
    end = datetime(2026, 3, 24)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).isoformat()


def generate_mock_issues(count=150):
    """Genere une liste d'issues simulees au format GitLab API."""
    random.seed(42)
    issues = []

    # Ponderation: certains modules ont plus de bugs
    weights = {
        "ARTICLE": 18, "COMMANDE": 16, "FACTURATION": 14, "STOCK": 12,
        "CLIENT": 10, "FOURNISSEUR": 5, "COMPTABILITE": 8, "LIVRAISON": 9,
        "PRODUCTION": 7, "TABLEAU DE BORD": 4, "UTILISATEUR": 3,
        "PARAMETRAGE": 6, "REPORTING": 5, "IMPORT/EXPORT": 7, "WORKFLOW": 4,
    }
    weighted_modules = []
    for mod, w in weights.items():
        weighted_modules.extend([mod] * w)

    for i in range(1, count + 1):
        module = random.choice(weighted_modules)
        suffix = random.choice(TITRES_SUFFIXES)
        is_prod = random.random() < 0.4  # 40% prod, 60% preprod
        label = PROD_LABEL if is_prod else PREPROD_LABEL
        state = random.choice(["closed"] * 7 + ["opened"] * 3)
        created = _random_date()

        issue = {
            "id": 1000 + i,
            "iid": i,
            "title": f"[{module}] {suffix}",
            "state": state,
            "labels": [label],
            "created_at": created,
            "updated_at": created,
            "web_url": f"https://gitlab.example.com/project/issues/{i}",
            "author": {"name": "Testeur QA", "username": "qa_testeur"},
        }
        issues.append(issue)

    # Ajouter quelques tickets sans module entre crochets
    for i in range(count + 1, count + 6):
        label = random.choice([PROD_LABEL, PREPROD_LABEL])
        issues.append({
            "id": 1000 + i,
            "iid": i,
            "title": "Bug général sans module identifié",
            "state": "closed",
            "labels": [label],
            "created_at": _random_date(),
            "updated_at": _random_date(),
            "web_url": f"https://gitlab.example.com/project/issues/{i}",
            "author": {"name": "Testeur QA", "username": "qa_testeur"},
        })

    return issues
