"""Données simulées pour le mode démo (pas de token GitLab)."""

import random
from datetime import datetime, timedelta

MODULES = ["ARTICLE", "COMMANDE", "STOCK", "EDI", "FACTURE", "CLIENT", "FOURNISSEUR", "LIVRAISON"]

# Pondération : certains modules ont plus de bugs
MODULE_WEIGHTS = {
    "ARTICLE": 12,
    "COMMANDE": 8,
    "STOCK": 6,
    "EDI": 7,
    "FACTURE": 5,
    "CLIENT": 3,
    "FOURNISSEUR": 2,
    "LIVRAISON": 4,
}

LABELS_PROD = ["Priorité::Immédiat prod", "Nature::Bug", "Retour::Retour prod"]
LABELS_PREPROD = ["Priorité::Urgent préprod", "Nature::Bug", "Retour::Retour préprod"]

DESCRIPTIONS = {
    "ARTICLE": [
        "Impossible de sauvegarder la fiche article",
        "Erreur de calcul du prix unitaire",
        "Le code-barres ne s'affiche pas",
        "Problème d'import des articles fournisseur",
        "Crash lors de la duplication d'article",
        "La TVA ne se calcule pas correctement",
        "Champ référence tronqué à 20 caractères",
    ],
    "COMMANDE": [
        "Crash à la validation de la commande",
        "Le montant total est incorrect",
        "Impossible d'annuler une commande validée",
        "Les lignes de commande disparaissent",
        "Erreur 500 à l'export PDF",
    ],
    "STOCK": [
        "Décalage de stock après inventaire",
        "Le mouvement de stock n'est pas enregistré",
        "Problème de réservation multi-dépôt",
        "Stock négatif non bloquant",
    ],
    "EDI": [
        "Erreur d'import du fichier EDI",
        "Le mapping des champs est incorrect",
        "Timeout lors de l'envoi EDI",
        "Doublons générés à l'import",
        "Format de date non reconnu dans le flux",
    ],
    "FACTURE": [
        "Le PDF de facture est vide",
        "Erreur d'arrondi sur la TVA",
        "Impossible de générer l'avoir",
        "Numérotation de facture en doublon",
    ],
    "CLIENT": [
        "La fiche client ne se charge pas",
        "Erreur lors de la fusion de doublons",
        "Le SIRET n'est pas validé",
    ],
    "FOURNISSEUR": [
        "Impossible de créer un nouveau fournisseur",
        "Le RIB ne s'enregistre pas",
    ],
    "LIVRAISON": [
        "Le bon de livraison ne s'imprime pas",
        "Erreur de calcul du poids total",
        "Problème de colisage automatique",
    ],
}

# Quelques tickets multi-modules
MULTI_MODULE_TICKETS = [
    {"modules": ["EDI", "ARTICLE"], "desc": "Problème d'import EDI sur les articles"},
    {"modules": ["EDI", "STOCK"], "desc": "Ajout des valeurs douanières dans l'import appro"},
    {"modules": ["COMMANDE", "FACTURE"], "desc": "Incohérence entre commande et facture générée"},
    {"modules": ["STOCK", "LIVRAISON"], "desc": "Décalage de stock après validation livraison"},
    {"modules": ["CLIENT", "COMMANDE"], "desc": "Erreur client lors de la création commande"},
    {"modules": ["EDI", "FOURNISSEUR"], "desc": "Mapping fournisseur incorrect dans flux EDI"},
]


def _random_date(year_start=2023, year_end=2026):
    """Générer une date aléatoire entre year_start et year_end."""
    start = datetime(year_start, 1, 1)
    end = datetime(year_end, 3, 24)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_mock_issues(count=50):
    """Générer des tickets simulés."""
    random.seed(42)
    issues = []
    iid_counter = 7000

    # Tickets mono-module
    weighted_modules = []
    for mod, weight in MODULE_WEIGHTS.items():
        weighted_modules.extend([mod] * weight)

    for i in range(count - len(MULTI_MODULE_TICKETS)):
        module = random.choice(weighted_modules)
        desc = random.choice(DESCRIPTIONS[module])
        is_prod = random.random() < 0.4  # 40% prod, 60% préprod
        labels = LABELS_PROD if is_prod else LABELS_PREPROD
        state = random.choice(["opened", "closed", "closed", "closed"])  # 75% fermés

        iid_counter += random.randint(1, 5)
        issues.append({
            "iid": iid_counter,
            "title": f"[{module}] {desc}",
            "state": state,
            "labels": labels,
            "created_at": _random_date(),
            "web_url": f"https://gitlab.example.fr/project/-/issues/{iid_counter}",
        })

    # Tickets multi-modules
    for ticket in MULTI_MODULE_TICKETS:
        is_prod = random.random() < 0.4
        labels = LABELS_PROD if is_prod else LABELS_PREPROD
        state = random.choice(["opened", "closed", "closed", "closed"])
        modules_str = "".join(f"[{m}]" for m in ticket["modules"])
        iid_counter += random.randint(1, 5)
        issues.append({
            "iid": iid_counter,
            "title": f"{modules_str} {ticket['desc']}",
            "state": state,
            "labels": labels,
            "created_at": _random_date(),
            "web_url": f"https://gitlab.example.fr/project/-/issues/{iid_counter}",
        })

    return issues
