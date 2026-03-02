"""
Progress endpoints — student history and aggregate statistics.

Single-user (no auth), so progress is simply all graded scenarios.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["progress"])


@router.get("/progress")
async def get_progress(request: Request) -> JSONResponse:
    """Get per-scenario grading history, newest first."""
    store = request.app.state.store
    progress = store.get_progress()
    return JSONResponse(content={"history": progress, "count": len(progress)})


@router.get("/progress/stats")
async def get_stats(request: Request) -> JSONResponse:
    """Get aggregate statistics across all graded scenarios."""
    store = request.app.state.store
    stats = store.get_summary_stats()
    return JSONResponse(content=stats)


@router.get("/progress/dashboard", response_class=HTMLResponse)
async def page_dashboard(request: Request) -> HTMLResponse:
    """Simple HTML dashboard showing progress summary."""
    store = request.app.state.store
    stats = store.get_summary_stats()
    history = store.get_progress()

    # Stats summary
    total = stats.get("total_scenarios", 0)
    graded = stats.get("total_graded", 0)
    avg_acc = stats.get("average_accuracy", 0)

    # Difficulty breakdown
    difficulty_rows = ""
    for diff, data in stats.get("by_difficulty", {}).items():
        difficulty_rows += (
            f'<tr><td>{diff}</td><td>{data["count"]}</td>'
            f'<td>{data["average_accuracy"]:.0%}</td></tr>\n'
        )

    # Recent history
    history_rows = ""
    for entry in history[:20]:
        accuracy = entry.get("accuracy", 0)
        if accuracy >= 0.9:
            color = "#4caf50"
        elif accuracy >= 0.7:
            color = "#ff9800"
        else:
            color = "#f44336"
        sid = entry.get("scenario_id", "")
        history_rows += (
            f'<tr>'
            f'<td><a href="/scenarios/{sid}">{sid[:12]}</a></td>'
            f'<td>{entry.get("mode", "")}</td>'
            f'<td>{entry.get("difficulty", "")}</td>'
            f'<td>{entry.get("score", 0)}/{entry.get("max_score", 0)}</td>'
            f'<td style="color:{color};font-weight:bold">{accuracy:.0%}</td>'
            f'<td>{entry.get("graded_at", "")[:16]}</td>'
            f'</tr>\n'
        )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Progress Dashboard — VITATrainer</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; }}
h2 {{ color: #2c5f8a; margin-top: 28px; }}
.stats {{ display: flex; gap: 24px; margin-bottom: 32px; }}
.stat-card {{ flex: 1; background: #f0f4f8; padding: 20px; border-radius: 8px; text-align: center; }}
.stat-number {{ font-size: 36px; font-weight: bold; color: #1a3a5c; }}
.stat-label {{ font-size: 14px; color: #555; margin-top: 4px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f0f4f8; }}
a {{ color: #2c5f8a; }}
.actions {{ margin-top: 32px; }}
.actions a {{ display: inline-block; padding: 12px 24px; background: #1a3a5c; color: white;
              text-decoration: none; border-radius: 4px; }}
.actions a:hover {{ background: #2c5f8a; }}
</style>
</head>
<body>
<h1>Progress Dashboard</h1>

<div class="stats">
    <div class="stat-card">
        <div class="stat-number">{total}</div>
        <div class="stat-label">Total Scenarios</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{graded}</div>
        <div class="stat-label">Graded</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{avg_acc:.0%}</div>
        <div class="stat-label">Average Accuracy</div>
    </div>
</div>

<h2>By Difficulty</h2>
<table>
<thead><tr><th>Difficulty</th><th>Count</th><th>Avg Accuracy</th></tr></thead>
<tbody>{difficulty_rows if difficulty_rows else "<tr><td colspan='3'>No graded scenarios yet</td></tr>"}</tbody>
</table>

<h2>Recent History</h2>
<table>
<thead><tr><th>Scenario</th><th>Mode</th><th>Difficulty</th><th>Score</th><th>Accuracy</th><th>Date</th></tr></thead>
<tbody>{history_rows if history_rows else "<tr><td colspan='6'>No graded scenarios yet</td></tr>"}</tbody>
</table>

<div class="actions">
    <a href="/scenarios/new">New Scenario</a>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)
