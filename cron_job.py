"""Script autonome pour la génération du rapport HTML statique.

Conçu pour être exécuté via le Planificateur de tâches Windows (ou cron Linux).
Exécution prévue : 13h00 et 19h00.

Usage:
    python cron_job.py
"""

import os
import json
from datetime import datetime
from config import config
from gitlab_client import fetch_issues, filter_bug_issues
from data_processor import process_issues

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "report.html")


def generate_report():
    """Générer le rapport HTML statique."""
    print(f"[{datetime.now()}] Récupération des données GitLab...")
    issues = fetch_issues()
    bug_issues = filter_bug_issues(issues)
    data = process_issues(bug_issues)
    data_all_years = data

    # Données par année
    current_year = datetime.now().year
    yearly_data = {}
    for year in range(2023, current_year + 1):
        yearly_data[year] = process_issues(bug_issues, year=year)

    print(f"[{datetime.now()}] {data['total']} bugs trouvés. Génération du rapport...")

    # Générer le HTML
    modules_json = json.dumps(data["modules_summary"])
    yearly_json = json.dumps({str(k): v for k, v in yearly_data.items()})

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>QA Bug Report — {datetime.now().strftime('%d/%m/%Y %H:%M')}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem; background: #f5f5f5; }}
        .header {{ background: #1a237e; color: white; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; }}
        .header h1 {{ margin: 0; }} .header p {{ margin: 0.5rem 0 0; opacity: 0.8; }}
        .card {{ background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
        .kpi {{ background: white; border-radius: 8px; padding: 1rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .kpi-val {{ font-size: 2rem; font-weight: 800; color: #1a237e; }}
        .kpi-lbl {{ font-size: 0.8rem; color: #888; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #1a237e; color: white; padding: 0.6rem; text-align: left; }}
        td {{ padding: 0.5rem 0.6rem; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f9f9f9; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QA Bug Report</h1>
        <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — Données depuis le 01/01/2023</p>
    </div>
    <div class="kpi-row">
        <div class="kpi"><div class="kpi-val">{data['total']}</div><div class="kpi-lbl">Total bugs</div></div>
        <div class="kpi"><div class="kpi-val" style="color:#e74c3c">{data['total_prod']}</div><div class="kpi-lbl">Retours Prod</div></div>
        <div class="kpi"><div class="kpi-val" style="color:#f39c12">{data['total_preprod']}</div><div class="kpi-lbl">Retours Préprod</div></div>
        <div class="kpi"><div class="kpi-val">{len(data['modules_summary'])}</div><div class="kpi-lbl">Modules touchés</div></div>
    </div>
    <div class="card">
        <h2>Bugs par module (cumulé)</h2>
        <div id="chart" style="height:400px;"></div>
    </div>
    <div class="card">
        <h2>Détail par module</h2>
        <table>
            <thead><tr><th>Module</th><th>Prod</th><th>Préprod</th><th>Total</th><th>%</th></tr></thead>
            <tbody>
                {"".join(f'<tr><td><strong>{m["module"]}</strong></td><td>{m["prod"]}</td><td>{m["preprod"]}</td><td><strong>{m["total"]}</strong></td><td>{m["percentage"]}%</td></tr>' for m in data["modules_summary"])}
            </tbody>
        </table>
    </div>
    <script>
        const data = {modules_json};
        Plotly.newPlot('chart', [
            {{ x: data.map(m=>m.module), y: data.map(m=>m.prod), name: 'Prod', type: 'bar', marker: {{color:'#e74c3c'}} }},
            {{ x: data.map(m=>m.module), y: data.map(m=>m.preprod), name: 'Préprod', type: 'bar', marker: {{color:'#f39c12'}} }}
        ], {{ barmode:'stack', margin:{{b:80}}, legend:{{orientation:'h',y:1.1}} }}, {{responsive:true}});
    </script>
</body>
</html>"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[{datetime.now()}] Rapport généré : {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_report()
