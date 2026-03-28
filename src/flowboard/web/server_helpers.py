"""Pure helper functions for the FlowBoard web server.

These are module-level utilities with no state dependency — SSE formatting,
demo fixture location, demo config generation, and the loading page HTML.
"""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path


def sse_format(event: str, data: dict | str) -> str:
    """Format a Server-Sent Event message."""
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def locate_demo_fixture() -> Path:
    """Locate the bundled mock Jira fixture with path traversal protection."""
    project_root = Path(__file__).resolve().parents[3]

    candidates: list[Path] = []
    try:
        ref = (
            importlib.resources.files("flowboard")
            / ".."
            / ".."
            / ".."
            / "examples"
            / "fixtures"
            / "mock_jira_data.json"
        )
        candidates.append(Path(str(ref)))
    except (ImportError, TypeError, OSError):
        pass
    candidates.append(project_root / "examples" / "fixtures" / "mock_jira_data.json")
    candidates.append(Path("examples/fixtures/mock_jira_data.json"))

    for candidate in candidates:
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_root)
        except ValueError:
            continue
        return resolved

    raise FileNotFoundError("Demo fixture not found: examples/fixtures/mock_jira_data.json")


def build_demo_config_dict(
    output_path: str = "output/demo_dashboard.html",
    methodology: str = "scrum",
    locale: str = "en",
) -> dict:
    """Build a synthetic config dict for demo dashboard generation."""
    base: dict = {
        "jira": {"base_url": "https://demo.atlassian.net"},
        "locale": locale,
        "methodology": methodology,
        "output": {
            "path": output_path,
            "title": "FlowBoard Demo Dashboard",
            "company_name": "Acme Corp",
        },
        "teams": [
            {"key": "platform", "name": "Platform", "members": ["user-1", "user-2", "user-3"]},
            {"key": "frontend", "name": "Frontend", "members": ["user-4", "user-5"]},
            {"key": "backend", "name": "Backend", "members": ["user-6", "user-7"]},
        ],
        "thresholds": {"overload_points": 15, "aging_days": 10},
        "dashboard": {
            "branding": {
                "title": "FlowBoard Demo Dashboard",
                "subtitle": "Delivery & Workload Intelligence — Demo Mode",
                "primary_color": "#fb6400",
                "company_name": "Acme Corp",
            },
        },
    }

    if methodology == "scrum":
        base["dashboard"]["branding"]["subtitle"] = "Scrum Dashboard — Demo Mode"
        base["pi"] = {
            "enabled": True,
            "name": "PI 2026.1",
            "start_date": "2026-03-02",
            "sprints_per_pi": 5,
            "sprint_length_days": 10,
            "working_days": [1, 2, 3, 4, 5],
        }
    elif methodology == "kanban":
        base["dashboard"]["branding"]["subtitle"] = "Kanban Flow Dashboard — Demo Mode"
        base["dashboard"]["branding"]["primary_color"] = "#3b82f6"
        base["thresholds"]["wip_limit"] = 3
    elif methodology == "waterfall":
        base["dashboard"]["branding"]["subtitle"] = "Waterfall Project Dashboard — Demo Mode"
        base["dashboard"]["branding"]["primary_color"] = "#8b5cf6"

    return base


# ---------------------------------------------------------------------------
# Loading page (self-contained HTML served when no dashboard is ready yet)
# ---------------------------------------------------------------------------


def build_loading_page() -> str:
    """Return self-contained HTML that auto-starts analysis via SSE."""
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlowBoard — Loading</title>
<style>
  :root{--primary:#fb6400;--bg:#0f0f1a;--surface:#1a1a2e;--text:#e0e0e0}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);
       color:var(--text);display:flex;align-items:center;justify-content:center;
       min-height:100vh}
  .loader{text-align:center;max-width:520px;padding:2rem}
  .loader h1{font-size:1.5rem;margin-bottom:1rem}
  .loader .phase{color:var(--primary);font-size:1.1rem;margin-bottom:.5rem}
  .loader .detail{color:#999;font-size:.9rem}
  .spinner{width:40px;height:40px;border:4px solid var(--surface);
           border-top-color:var(--primary);border-radius:50%;margin:1rem auto;
           animation:spin .8s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .error{color:#ff4444}
  .actions{margin-top:1.5rem;display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap}
  .actions button{color:#fff;border:none;padding:8px 20px;
                  border-radius:6px;cursor:pointer;font-size:.9rem}
  .btn-primary{background:var(--primary)}
  .btn-secondary{background:#555}
  .actions button:hover{opacity:.85}
  .hint{color:#777;font-size:.8rem;margin-top:1rem}
</style>
</head>
<body>
<div class="loader">
  <h1>FlowBoard</h1>
  <div class="spinner" id="spinner"></div>
  <div class="phase" id="phase">Starting analysis\u2026</div>
  <div class="detail" id="detail"></div>
  <div class="actions" id="actions" style="display:none">
    <button class="btn-primary" onclick="triggerAnalysis()">Retry Analysis</button>
    <button class="btn-secondary" onclick="triggerDemo()">Load Demo Dashboard</button>
  </div>
  <div class="hint" id="hint" style="display:none"></div>
</div>
<script>
const _PHASE_LABELS={idle:'Starting\u2026',fetching:'Fetching data from Jira\u2026',analyzing:'Analyzing\u2026',rendering:'Rendering dashboard\u2026',completed:'Done!',failed:'Analysis failed'};
const _H={'X-Requested-With':'FlowBoard','Content-Type':'application/json'};

function showActions(withHint){
  document.getElementById('actions').style.display='';
  const hint=document.getElementById('hint');
  if(withHint){hint.textContent='Tip: If your Jira credentials are not configured yet, try Demo Dashboard to explore FlowBoard.';hint.style.display='';}
}

function hideActions(){
  document.getElementById('actions').style.display='none';
  document.getElementById('hint').style.display='none';
}

function showErr(msg){
  const el=document.getElementById('detail');el.textContent='';
  const s=document.createElement('span');s.className='error';s.textContent=msg;
  el.appendChild(s);showActions(true);
}

function resetSpinner(){
  const sp=document.getElementById('spinner');
  sp.style.display='';sp.style.borderTopColor='var(--primary)';
  sp.style.animationPlayState='running';
}

function connectSSE(){
  const es=new EventSource('/api/analyze/stream');
  const phase=document.getElementById('phase');
  const detail=document.getElementById('detail');
  const spinner=document.getElementById('spinner');
  function update(d){
    phase.textContent=_PHASE_LABELS[d.phase]||d.phase||'';
    detail.textContent=d.detail||'';
    if(d.error){showErr(d.error);}
  }
  es.addEventListener('current_state',function(e){
    const d=JSON.parse(e.data);
    update(d);
    if(d.phase==='idle'){triggerAnalysis();}
    else if(d.phase==='failed'){showActions(true);}
  });
  es.addEventListener('analysis_progress',e=>update(JSON.parse(e.data)));
  es.addEventListener('analysis_complete',e=>{
    update(JSON.parse(e.data));spinner.style.display='none';es.close();
    setTimeout(()=>window.location.reload(),500);
  });
  es.addEventListener('analysis_failed',e=>{
    update(JSON.parse(e.data));
    spinner.style.borderTopColor='#ff4444';
    spinner.style.animationPlayState='paused';es.close();
    showActions(true);
  });
  es.onerror=()=>{detail.textContent='Connection lost. Retrying\u2026'};
}

async function triggerAnalysis(){
  hideActions();resetSpinner();
  document.getElementById('phase').textContent='Starting analysis\u2026';
  document.getElementById('detail').textContent='';
  try{
    const r=await fetch('/api/analyze',{method:'POST',headers:_H});
    if(r.ok){window.location.reload();}
    else{const d=await r.json();showErr(d.error||'Analysis failed');}
  }catch(e){showErr(e.message);}
}

async function triggerDemo(){
  hideActions();resetSpinner();
  document.getElementById('phase').textContent='Generating demo dashboard\u2026';
  document.getElementById('detail').textContent='';
  try{
    const r=await fetch('/api/demo',{method:'POST',headers:_H,body:'{}'});
    if(r.ok){window.location.reload();}
    else{const d=await r.json();showErr(d.error||'Demo generation failed');}
  }catch(e){showErr(e.message);}
}

connectSSE();
</script>
</body>
</html>"""
