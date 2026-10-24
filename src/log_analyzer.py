"""Parse synthetic log lines into events, incident candidates and a reproducible summary."""
from __future__ import annotations
import argparse
import csv
import json
import shlex
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = ['timestamp', 'router', 'vendor', 'severity', 'event_type', 'interface', 'message']
LEVELS = {'CRITICAL', 'MAJOR', 'MINOR', 'WARNING', 'INFO'}

def parse_line(line, number=0):
    raw = line.strip()
    if not raw or raw.startswith('#'):
        return None
    parts = shlex.split(raw)
    if not parts:
        return None
    # Intentionally defined example format rather than universal vendor syslog parsing.
    try:
        dt = datetime.fromisoformat(parts[0].replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'line {number}: invalid ISO timestamp') from exc
    if dt.tzinfo is None:
        raise ValueError(f'line {number}: timestamp needs timezone')
    fields = {}
    for part in parts[1:]:
        if '=' not in part:
            raise ValueError(f'line {number}: expected key=value: {part}')
        key, value = part.split('=', 1)
        fields[key] = value
    required = ('router', 'vendor', 'severity', 'code', 'interface', 'message')
    if any(not fields.get(x) for x in required):
        raise ValueError(f'line {number}: missing required field')
    sev = fields['severity'].upper()
    if sev not in LEVELS:
        raise ValueError(f'line {number}: unknown severity {sev}')
    return dict(timestamp=dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                router=fields['router'], vendor=fields['vendor'], severity=sev,
                event_type=fields['code'], interface=fields['interface'], message=fields['message'])

def analyze_lines(lines):
    events, errors = [], []
    for n, line in enumerate(lines, 1):
        try:
            event = parse_line(line, n)
            if event:
                events.append(event)
        except ValueError as exc:
            errors.append(str(exc))
    events.sort(key=lambda e: (e['timestamp'], e['router'], e['event_type']))
    counts = Counter(e['severity'] for e in events)
    kinds = Counter(e['event_type'] for e in events)
    devices = Counter(e['router'] for e in events)
    # Not a root cause conclusion: candidate clusters by exact device/interface/event type.
    groups = {}
    for e in events:
        key = (e['router'], e['interface'], e['event_type'])
        groups.setdefault(key, []).append(e)
    incident_candidates = [dict(router=k[0], interface=k[1], event_type=k[2],
                                first_seen=v[0]['timestamp'], last_seen=v[-1]['timestamp'],
                                occurrences=len(v), severity=v[0]['severity'])
                           for k,v in sorted(groups.items())]
    summary = {'data_source': 'SYNTHETIC / DEMONSTRATION ONLY',
               'total_events': len(events), 'invalid_lines': len(errors),
               'by_severity': dict(sorted(counts.items())),
               'by_event_type': dict(sorted(kinds.items())),
               'by_router': dict(sorted(devices.items())),
               'incident_candidates': incident_candidates,
               'limitations': 'Event clusters are exact-key matches, not validated incidents or automatic root-cause analysis.'}
    return events, summary, errors

def save(events, summary, errors, output_dir):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir/'events.csv').open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(events)
    (output_dir/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir/'parse_errors.txt').write_text('\n'.join(errors) + ('\n' if errors else ''), encoding='utf-8')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=Path('data/sample_network.log'))
    ap.add_argument('--out-dir', type=Path, default=Path('outputs'))
    args = ap.parse_args()
    events, summary, errors = analyze_lines(args.input.read_text(encoding='utf-8').splitlines())
    save(events, summary, errors, args.out_dir)
    print(f'Parsed {len(events)} events, rejected {len(errors)} malformed lines. Saved to {args.out_dir}')
if __name__ == '__main__':
    main()
