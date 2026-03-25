"""
Export de la matrice des risques en fichier Excel formate.
"""

import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


RISK_FILLS = {
    "critique": PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid"),
    "eleve": PatternFill(start_color="E67E22", end_color="E67E22", fill_type="solid"),
    "moyen": PatternFill(start_color="F1C40F", end_color="F1C40F", fill_type="solid"),
    "faible": PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid"),
    "non_evalue": PatternFill(start_color="95A5A6", end_color="95A5A6", fill_type="solid"),
}

IMPACT_FILLS = {
    "critique": PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid"),
    "majeur": PatternFill(start_color="E67E22", end_color="E67E22", fill_type="solid"),
    "modere": PatternFill(start_color="F1C40F", end_color="F1C40F", fill_type="solid"),
    "mineur": PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid"),
    "non_defini": PatternFill(start_color="95A5A6", end_color="95A5A6", fill_type="solid"),
}

HEADER_FILL = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14)
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def export_risk_matrix_to_excel(matrix_info, risk_data):
    """
    Genere un fichier Excel avec la matrice des risques.
    Retourne un BytesIO buffer.
    """
    wb = Workbook()

    # --- Feuille 1 : Matrice des risques ---
    ws = wb.active
    ws.title = "Matrice des Risques"

    # Titre
    ws.merge_cells("A1:I1")
    ws["A1"] = f"Matrice des Risques ISTQB - {matrix_info['version']}"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:I2")
    ws["A2"] = f"Description : {matrix_info.get('description', '')}"
    ws["A2"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A3:I3")
    ws["A3"] = f"Date de création : {matrix_info.get('created_at', '')}"
    ws["A3"].alignment = Alignment(horizontal="center")

    # En-tetes
    headers = [
        "Module", "Bugs Prod", "Bugs Préprod", "Total Bugs", "% du Total",
        "Probabilité", "Impact", "Niveau de Risque", "Commentaire",
    ]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = THIN_BORDER

    # Donnees
    for row_idx, item in enumerate(risk_data, 6):
        values = [
            item["module"],
            item["prod_count"],
            item["preprod_count"],
            item["bug_count"],
            f"{item['percentage']}%",
            item["probability_label"],
            item["impact_label"],
            item["risk_label"],
            item.get("comment", ""),
        ]
        for col_idx, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        # Couleur du niveau de risque
        risk_cell = ws.cell(row=row_idx, column=8)
        risk_fill = RISK_FILLS.get(item["risk_key"])
        if risk_fill:
            risk_cell.fill = risk_fill
            if item["risk_key"] in ("critique", "eleve"):
                risk_cell.font = Font(color="FFFFFF", bold=True)

        # Couleur de l'impact
        impact_cell = ws.cell(row=row_idx, column=7)
        impact_fill = IMPACT_FILLS.get(item["impact_key"])
        if impact_fill:
            impact_cell.fill = impact_fill
            if item["impact_key"] in ("critique", "majeur"):
                impact_cell.font = Font(color="FFFFFF", bold=True)

    # Largeurs de colonnes
    widths = [20, 12, 14, 12, 12, 16, 12, 18, 30]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # --- Feuille 2 : Legende ISTQB ---
    ws2 = wb.create_sheet("Légende ISTQB")

    ws2["A1"] = "Échelle de Probabilité (basée sur la fréquence des bugs)"
    ws2["A1"].font = Font(bold=True, size=12)
    ws2.merge_cells("A1:C1")

    prob_headers = ["Niveau", "Seuil (%)", "Description"]
    for col, h in enumerate(prob_headers, 1):
        cell = ws2.cell(row=3, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER

    prob_data = [
        ("Très élevée", "≥ 20%", "Module concentrant une part très importante des bugs"),
        ("Élevée", "≥ 12%", "Module avec une fréquence élevée de bugs"),
        ("Moyenne", "≥ 6%", "Module avec une fréquence modérée de bugs"),
        ("Faible", "≥ 2%", "Module avec peu de bugs"),
        ("Très faible", "< 2%", "Module rarement affecté par les bugs"),
    ]
    for row_idx, (level, threshold, desc) in enumerate(prob_data, 4):
        for col_idx, val in enumerate([level, threshold, desc], 1):
            cell = ws2.cell(row=row_idx, column=col_idx, value=val)
            cell.border = THIN_BORDER

    ws2["A10"] = "Échelle d'Impact (saisie manuelle)"
    ws2["A10"].font = Font(bold=True, size=12)

    impact_headers = ["Niveau", "Description"]
    for col, h in enumerate(impact_headers, 1):
        cell = ws2.cell(row=12, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER

    impact_data = [
        ("Critique", "Impact business majeur, perte de données, indisponibilité totale"),
        ("Majeur", "Fonctionnalité clé inutilisable, contournement difficile"),
        ("Modéré", "Fonctionnalité dégradée, contournement possible"),
        ("Mineur", "Gêne mineure, impact cosmétique ou ergonomique"),
    ]
    for row_idx, (level, desc) in enumerate(impact_data, 13):
        for col_idx, val in enumerate([level, desc], 1):
            cell = ws2.cell(row=row_idx, column=col_idx, value=val)
            cell.border = THIN_BORDER

    for col in range(1, 4):
        ws2.column_dimensions[get_column_letter(col)].width = 25

    # Ecrire dans un buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
