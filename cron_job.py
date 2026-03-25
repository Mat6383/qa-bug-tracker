"""
Script autonome pour generation du rapport HTML statique.
A executer via cron/Task Scheduler a 13h et 19h.

Usage:
    python cron_job.py
"""

import os
import json
from datetime import datetime
from config import Config
from database import init_db
from gitlab_client import fetch_all_bug_issues
from data_processor import process_issues


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport Bugs ERP - {date}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #2c3e50; padding: 2rem; }}
        .header {{ text-align: center; margin-bottom: 2rem; }}
        .header h1 {{ font-size: 1.8rem; }}
        .header p {{ color: #7f8c8d; }}
        .kpi-row {{ display: flex; gap: 1rem; justify-content: center; margin-bottom: 2rem; flex-wrap: wrap; }}
        .kpi {{ background: white; border-radius: 10px; padding: 1rem 2rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .kpi-value {{ font-size: 2rem; font-weight: 700; }}
        .kpi-label {{ font-size: 0.85rem; color: #7f8c8d; }}
        .card {{ background: white; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .card h2 {{ font-size: 1.2rem; margin-bottom: 1rem; border-bottom: 2px solid #f0f2f5; padding-bottom: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
        th {{ background: #2c3e50; color: white; padding: 0.7rem; }}
        td {{ padding: 0.6rem; text-align: center; border-bottom: 1px solid #ecf0f1; }}
        tr:hover {{ background: #f8f9fa; }}
        .prod {{ color: #e74c3c; font-weight: 600; }}
        .preprod {{ color: #f39c12; font-weight: 600; }}
        .chart {{ min-height: 400px; }}
        .footer {{ text-align: center; color: #95a5a6; margin-top: 2rem; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Rapport Bugs ERP</h1>
        <p>Genere automatiquement le {date} | Donnees depuis janvier 2023</p>
        <p>{mode}</p>
    </div>

    <div class="kpi-row">
        <div class="kpi"><div class="kpi-value">{total}</div><div class="kpi-label">Total bugs</div></div>
        <div class="kpi"><div class="kpi-value prod">{total_prod}</div><div class="kpi-label">Production</div></div>
        <div class="kpi"><div class="kpi-value preprod">{total_preprod}</div><div class="kpi-label">Preproduction</div></div>
        <div class="kpi"><div class="kpi-value">{nb_modules}</div><div class="kpi-label">Modules</div></div>
    </div>

    <div class="card">
        <h2>Repartition des bugs par module</h2>
        <div id="chart" class="chart"></div>
    </div>

    <div class="card">
        <h2>Detail par module</h2>
        <table>
            <thead><tr><th>Rang</th><th>Module</th><th>Prod</th><th>Preprod</th><th>Total</th><th>%</th></tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>

    <div class="footer">QA Bug Tracker - Rapport automatique</div>

    <script>
        var data = {chart_data};
        var traces = [
            {{ x: data.modules, y: data.prod, name: 'Production', type: 'bar', marker: {{ color: '#e74c3c' }} }},
            {{ x: data.modules, y: data.preprod, name: 'Preproduction', type: 'bar', marker: {{ color: '#f39c12' }} }}
        ];
        Plotly.newPlot('chart', traces, {{
            barmode: 'stack',
            xaxis: {{ tickangle: -45 }},
            yaxis: {{ title: 'Nombre de bugs' }},
            margin: {{ b: 120, t: 20 }},
            legend: {{ orientation: 'h', y: 1.1 }}
        }});
    </script>
</body>
</html>"""


def generate_report():
    """Genere le rapport HTML statique."""
    print(f"[{datetime.now()}] Debut de la generation du rapport...")

    init_db()
    issues = fetch_all_bug_issues()
    data = process_issues(issues)

    # Preparer les donnees pour le graphique
    modules_list = [m for m, _ in data["modules_ranked"]]
    prod_list = [s["prod"] for _, s in data["modules_ranked"]]
    preprod_list = [s["preprod"] for _, s in data["modules_ranked"]]

    chart_data = json.dumps({
        "modules": modules_list,
        "prod": prod_list,
        "preprod": preprod_list,
    })

    # Generer les lignes du tableau
    table_rows = ""
    for i, (module, stats) in enumerate(data["modules_ranked"], 1):
        table_rows += (
            f'<tr><td>{i}</td><td><strong>{module}</strong></td>'
            f'<td class="prod">{stats["prod"]}</td>'
            f'<td class="preprod">{stats["preprod"]}</td>'
            f'<td><strong>{stats["total"]}</strong></td>'
            f'<td>{stats["percentage"]}%</td></tr>\n'
        )

    total_prod = sum(s["prod"] for _, s in data["modules_ranked"])
    total_preprod = sum(s["preprod"] for _, s in data["modules_ranked"])

    mode = "Mode DEMO (donnees simulees)" if not Config.is_gitlab_configured() else "GitLab connecte"

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%d/%m/%Y a %H:%M"),
        total=data["total_issues"],
        total_prod=total_prod,
        total_preprod=total_preprod,
        nb_modules=len(data["modules_ranked"]),
        table_rows=table_rows,
        chart_data=chart_data,
        mode=mode,
    )

    # Ecrire le fichier
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(Config.OUTPUT_DIR, "report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[{datetime.now()}] Rapport genere: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_report()
