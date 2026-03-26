"""
Script autonome : fetch GitLab + génération rapport HTML statique.
Lancé 2x/jour par le planificateur Windows (13h et 19h).

Usage manuel :
    python cron_job.py
"""

import os
import sys
import json
import logging
from datetime import datetime

# Ajouter le répertoire du script au path (important pour Task Scheduler)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import init_db
from gitlab_client import fetch_all_bug_issues
from data_processor import process_issues


# ─── Logging ──────────────────────────────────────────────────────────────────

os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
LOG_FILE = os.path.join(Config.OUTPUT_DIR, "cron.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("cron_job")


# ─── Template HTML rapport statique ───────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport Bugs ERP — {date}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif; background:#f0f2f5; color:#333; padding:2rem; }}
        .header {{ text-align:center; margin-bottom:2rem; }}
        .header h1 {{ font-size:1.8rem; color:#1a237e; }}
        .header p {{ color:#888; margin-top:.3rem; }}
        .badge {{ display:inline-block; background:#e8f5e9; color:#2e7d32; border-radius:20px;
                  padding:.2rem .8rem; font-size:.85rem; font-weight:600; margin-top:.5rem; }}
        .kpi-row {{ display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; margin-bottom:2rem; }}
        .kpi {{ background:white; border-radius:10px; padding:1.2rem 2rem; text-align:center;
                box-shadow:0 2px 8px rgba(0,0,0,.08); border-top:4px solid #1a237e; }}
        .kpi.prod {{ border-top-color:#e74c3c; }}
        .kpi.preprod {{ border-top-color:#f39c12; }}
        .kpi-value {{ font-size:2.2rem; font-weight:800; color:#1a237e; }}
        .kpi.prod .kpi-value {{ color:#e74c3c; }}
        .kpi.preprod .kpi-value {{ color:#f39c12; }}
        .kpi-label {{ font-size:.8rem; color:#888; text-transform:uppercase; letter-spacing:.5px; margin-top:.2rem; }}
        .card {{ background:white; border-radius:10px; padding:1.5rem; margin-bottom:1.5rem;
                 box-shadow:0 2px 8px rgba(0,0,0,.08); }}
        .card h2 {{ font-size:1.1rem; color:#1a237e; margin-bottom:1rem;
                    padding-bottom:.5rem; border-bottom:2px solid #e8eaf6; }}
        table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
        th {{ background:#1a237e; color:white; padding:.7rem 1rem; text-align:left; }}
        td {{ padding:.6rem 1rem; border-bottom:1px solid #e0e0e0; }}
        tr:hover {{ background:#f5f5f5; }}
        .center {{ text-align:center; }}
        .prod-val {{ color:#e74c3c; font-weight:600; }}
        .preprod-val {{ color:#f39c12; font-weight:600; }}
        .footer {{ text-align:center; color:#aaa; font-size:.8rem; margin-top:2rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Rapport Bugs ERP</h1>
        <p>Généré automatiquement le {date}</p>
        <p>Données depuis janvier 2023 · {mode}</p>
    </div>

    <div class="kpi-row">
        <div class="kpi">
            <div class="kpi-value">{total}</div>
            <div class="kpi-label">Total Bugs</div>
        </div>
        <div class="kpi prod">
            <div class="kpi-value">{total_prod}</div>
            <div class="kpi-label">Retours Prod</div>
        </div>
        <div class="kpi preprod">
            <div class="kpi-value">{total_preprod}</div>
            <div class="kpi-label">Retours Préprod</div>
        </div>
        <div class="kpi">
            <div class="kpi-value">{nb_modules}</div>
            <div class="kpi-label">Modules</div>
        </div>
    </div>

    <div class="card">
        <h2>Répartition des bugs par module (cumulé depuis 2023)</h2>
        <div id="chart" style="height:480px;"></div>
    </div>

    <div class="card">
        <h2>Détail par module</h2>
        <table>
            <thead>
                <tr>
                    <th>Rang</th>
                    <th>Module</th>
                    <th class="center">Bugs Prod</th>
                    <th class="center">Bugs Préprod</th>
                    <th class="center">Total</th>
                    <th class="center">% du total</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>

    <div class="footer">QA Bug Tracker — Rapport automatique ISTQB</div>

    <script>
        var chartData = {chart_data};
        Plotly.newPlot('chart', [
            {{ x: chartData.modules, y: chartData.prod,   name: 'Retours Prod',   type: 'bar', marker: {{ color: '#e74c3c' }} }},
            {{ x: chartData.modules, y: chartData.preprod, name: 'Retours Préprod', type: 'bar', marker: {{ color: '#f39c12' }} }}
        ], {{
            barmode: 'stack',
            xaxis: {{ tickangle: -40 }},
            yaxis: {{ title: 'Nombre de bugs' }},
            margin: {{ b: 130, t: 10 }},
            legend: {{ orientation: 'h', y: 1.08 }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: '#ffffff'
        }}, {{ responsive: true }});
    </script>
</body>
</html>"""


# ─── Génération du rapport HTML ───────────────────────────────────────────────

def generate_report(issues=None):
    """
    Génère le rapport HTML statique dans output/report.html.
    Si issues est fourni (depuis le cache app), évite un double appel GitLab.
    """
    if issues is None:
        log.info("Fetch des issues GitLab...")
        issues = fetch_all_bug_issues()

    log.info(f"{len(issues)} issues récupérées.")
    data = process_issues(issues)

    modules_ranked = data["modules_ranked"]
    modules_list  = [m for m, _ in modules_ranked]
    prod_list     = [s["prod"]    for _, s in modules_ranked]
    preprod_list  = [s["preprod"] for _, s in modules_ranked]

    chart_data = json.dumps({"modules": modules_list, "prod": prod_list, "preprod": preprod_list})

    table_rows = ""
    for i, (module, stats) in enumerate(modules_ranked, 1):
        table_rows += (
            f'<tr>'
            f'<td class="center">{i}</td>'
            f'<td><strong>{module}</strong></td>'
            f'<td class="center prod-val">{stats["prod"]}</td>'
            f'<td class="center preprod-val">{stats["preprod"]}</td>'
            f'<td class="center"><strong>{stats["total"]}</strong></td>'
            f'<td class="center">{stats["percentage"]}%</td>'
            f'</tr>\n'
        )

    mode = "Mode DEMO (données simulées)" if not Config.is_gitlab_configured() else "GitLab connecté"

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%d/%m/%Y à %H:%M"),
        total=data["total"],
        total_prod=data["total_prod"],
        total_preprod=data["total_preprod"],
        nb_modules=len(modules_ranked),
        table_rows=table_rows,
        chart_data=chart_data,
        mode=mode,
    )

    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(Config.OUTPUT_DIR, "report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Rapport HTML généré : {output_path}")
    return output_path


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def run():
    log.info("=== Démarrage cron QA Bug Tracker ===")
    try:
        init_db()
        issues = fetch_all_bug_issues()
        generate_report(issues=issues)
        log.info("=== Cron terminé avec succès ===")
    except Exception as e:
        log.error(f"Erreur cron : {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
