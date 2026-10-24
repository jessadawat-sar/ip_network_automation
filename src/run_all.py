"""Reproducible end-to-end: topology simulation -> synthetic logs -> analyzer -> dashboard."""
from pathlib import Path
import json
from backbone import DEFAULT_TOPOLOGY, scenario, synthetic_logs, make_svg
from log_analyzer import analyze_lines, save
from dashboard import build_dashboard
import csv

def run(repo_root=None):
    root = Path(repo_root or Path(__file__).resolve().parents[1])
    out = root / 'outputs'; data = root / 'data'; out.mkdir(exist_ok=True, parents=True); data.mkdir(exist_ok=True, parents=True)
    topology = DEFAULT_TOPOLOGY
    (data/'topology.json').write_text(json.dumps(topology, indent=2), encoding='utf-8')
    report = scenario(topology)
    (out/'backbone_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    make_svg(topology, report, out/'backbone_topology.svg')
    sample = synthetic_logs(topology)
    (data/'sample_network.log').write_text('# SYNTHETIC router event records - never a real carrier log\n'+'\n'.join(sample)+'\n', encoding='utf-8')
    events, summary, errors = analyze_lines(sample)
    save(events, summary, errors, out)
    (out/'network_dashboard.html').write_text(build_dashboard(events, summary), encoding='utf-8')
    print(f'Route BEFORE: {" -> ".join(report["before"]["path"])} , cost={report["before"]["total_cost"]}')
    print(f'Route AFTER : {" -> ".join(report["after"]["path"])} , cost={report["after"]["total_cost"]}')
    print(f'Processed {summary["total_events"]} synthetic events, invalid={summary["invalid_lines"]}')
    print('Dashboard:', out/'network_dashboard.html')
    return report, summary
if __name__=='__main__':
    run()
