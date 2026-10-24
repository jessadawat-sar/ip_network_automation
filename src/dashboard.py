"""Generate an offline interactive HTML dashboard using exported analysis data."""
from __future__ import annotations
import argparse
import csv
import html
import json
from pathlib import Path

# Inline JS and CSS only: no remote libraries, calls, or runtime services.
HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Network Fault Analysis | Demo</title><style>
:root{font-family:Arial,sans-serif;color:#15324e;background:#f2f6fb}*{box-sizing:border-box}body{margin:0}header{background:#123754;color:#fff;padding:25px max(22px,calc((100vw - 1150px)/2))}h1{font-size:26px;margin:4px 0}header p{color:#b9daeb;margin:3px 0}main{max-width:1150px;margin:25px auto;padding:0 20px} .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric,.panel{background:white;border:1px solid #dfe8f1;border-radius:12px;padding:18px;box-shadow:0 4px 14px rgba(15,40,70,.04)}.metric strong{display:block;font-size:32px;color:#0a728e;margin:6px 0}.metric span,.muted{font-size:13px;color:#60758a}.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.panel h2{font-size:17px;margin:0 0 18px}.barrow{display:flex;align-items:center;gap:12px;margin:12px 0}.barrow label{min-width:132px;font-size:13px}.bartrack{height:17px;background:#e9f2f8;border-radius:6px;flex:1}.bar{height:100%;border-radius:6px;background:#1686a5}.count{width:34px;text-align:right;font-size:13px;font-weight:bold}table{width:100%;border-collapse:collapse;background:white;font-size:12px}td,th{padding:10px 9px;border-bottom:1px solid #e5edf4;text-align:left}th{background:#e9f2f7;color:#24516d}.controls{display:flex;align-items:center;gap:14px;margin:18px 0}select{padding:8px 12px;border:1px solid #b9cbdc;border-radius:7px} .tag{display:inline-block;padding:4px 7px;border-radius:6px;background:#e2edf6} .footer{font-size:12px;margin:24px 0;color:#617384}@media(max-width:720px){.metrics,.cols{grid-template-columns:1fr 1fr}.barrow label{min-width:95px}}@media(max-width:480px){.metrics,.cols{grid-template-columns:1fr}}
</style></head><body><header><p>IP BACKBONE / NETWORK OPERATIONS PORTFOLIO</p><h1>Network Fault & Alarm Analysis</h1><p>Offline synthetic demo • Events are fictional • Not connected to production systems</p></header><main>
<div class="metrics"><div class="metric"><span>Total events</span><strong id="metric-total"></strong></div><div class="metric"><span>Major events</span><strong id="metric-major"></strong></div><div class="metric"><span>Devices observed</span><strong id="metric-devices"></strong></div><div class="metric"><span>Candidate clusters</span><strong id="metric-clusters"></strong></div></div>
<div class="cols"><section class="panel"><h2>Events by severity</h2><div id="sev-bars"></div></section><section class="panel"><h2>Events by router</h2><div id="router-bars"></div></section></div>
<section class="panel" style="margin-top:18px"><h2>Event timeline</h2><div class="controls"><label for="sev-select">Severity filter</label><select id="sev-select"><option value="ALL">All severities</option><option>MAJOR</option><option>WARNING</option><option>MINOR</option><option>INFO</option></select><span id="shown" class="muted"></span></div><div style="overflow:auto"><table><thead><tr><th>UTC time</th><th>Severity</th><th>Router</th><th>Interface</th><th>Event</th><th>Message</th></tr></thead><tbody id="event-table"></tbody></table></div></section>
<p class="footer">Interpretation note: Exact-key event clusters are candidate correlations, NOT proven root causes. This is a local static HTML artifact generated from simulated data.</p></main>
<script>const DATA=__DATA__;
function makeBars(container,obj){const entries=Object.entries(obj);const max=Math.max(1,...entries.map(x=>x[1]));const el=document.getElementById(container);el.innerHTML='';entries.forEach(([name,value])=>{const row=document.createElement('div');row.className='barrow';const label=document.createElement('label');label.textContent=name;const track=document.createElement('div');track.className='bartrack';const bar=document.createElement('div');bar.className='bar';bar.style.width=(100*value/max)+'%';track.appendChild(bar);const count=document.createElement('span');count.className='count';count.textContent=value;row.append(label,track,count);el.appendChild(row);});}
function render(){const sev=document.getElementById('sev-select').value;const arr=DATA.events.filter(e=>sev==='ALL'||e.severity===sev);const body=document.getElementById('event-table');body.innerHTML='';arr.forEach(e=>{const tr=document.createElement('tr');[e.timestamp,e.severity,e.router,e.interface,e.event_type,e.message].forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;tr.appendChild(td);});body.appendChild(tr);});document.getElementById('shown').textContent=arr.length+' shown';}
const s=DATA.summary;document.getElementById('metric-total').textContent=s.total_events;document.getElementById('metric-major').textContent=s.by_severity.MAJOR||0;document.getElementById('metric-devices').textContent=Object.keys(s.by_router).length;document.getElementById('metric-clusters').textContent=s.incident_candidates.length;makeBars('sev-bars',s.by_severity);makeBars('router-bars',s.by_router);document.getElementById('sev-select').addEventListener('change',render);render();
</script></body></html>'''

def build_dashboard(events, summary):
    # JSON can contain untrusted strings in future; escape HTML-significant script terminators.
    payload = json.dumps({'events': events, 'summary': summary}, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return HTML.replace('__DATA__', payload)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--events', type=Path, default=Path('outputs/events.csv'))
    ap.add_argument('--summary', type=Path, default=Path('outputs/summary.json'))
    ap.add_argument('--output', type=Path, default=Path('outputs/network_dashboard.html'))
    args=ap.parse_args()
    with args.events.open(encoding='utf-8-sig', newline='') as fp:
        events=list(csv.DictReader(fp))
    summary=json.loads(args.summary.read_text(encoding='utf-8'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(build_dashboard(events,summary),encoding='utf-8')
    print(f'Wrote {args.output} (open locally in a browser)')
if __name__ == '__main__':
    main()
