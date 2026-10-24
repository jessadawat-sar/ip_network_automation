"""Offline weighted IP-backbone graph simulator (NOT a router OS or BGP/OSPF emulator)."""
from __future__ import annotations
import argparse
import json
import heapq
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_TOPOLOGY = {
    "nodes": [
        {"id": "BKK-CORE-1", "vendor": "Cisco"},
        {"id": "BKK-CORE-2", "vendor": "Juniper"},
        {"id": "CBI-AGG-1", "vendor": "Huawei"},
        {"id": "AYA-AGG-1", "vendor": "Nokia"},
        {"id": "RYG-EDGE-1", "vendor": "ZTE"},
    ],
    "links": [
        {"a": "BKK-CORE-1", "b": "CBI-AGG-1", "cost": 10, "interface_a": "Eth1/1", "interface_b": "GE0/0/1"},
        {"a": "CBI-AGG-1", "b": "RYG-EDGE-1", "cost": 10, "interface_a": "GE0/0/2", "interface_b": "GE0/1/0"},
        {"a": "BKK-CORE-1", "b": "BKK-CORE-2", "cost": 8, "interface_a": "Eth1/2", "interface_b": "xe-0/0/0"},
        {"a": "BKK-CORE-2", "b": "AYA-AGG-1", "cost": 12, "interface_a": "xe-0/0/1", "interface_b": "1/1/1"},
        {"a": "AYA-AGG-1", "b": "RYG-EDGE-1", "cost": 18, "interface_a": "1/1/2", "interface_b": "GE0/1/1"},
    ],
}

def validate_topology(topology):
    ids = [n["id"] for n in topology["nodes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate node id")
    for e in topology["links"]:
        if e["a"] not in ids or e["b"] not in ids or e["a"] == e["b"]:
            raise ValueError("Invalid link endpoints")
        if not isinstance(e["cost"], (int, float)) or e["cost"] <= 0:
            raise ValueError("Link costs must be positive")

def shortest_path(topology, source, destination, failed_links=()):
    """Undirected Dijkstra by abstract positive cost, not real routing control plane."""
    validate_topology(topology)
    ids = {n["id"] for n in topology["nodes"]}
    if source not in ids or destination not in ids:
        raise ValueError("Unknown router")
    failure_set = {frozenset(pair) for pair in failed_links}
    graph = {name: [] for name in ids}
    for edge in topology["links"]:
        if frozenset((edge["a"], edge["b"])) in failure_set:
            continue
        graph[edge["a"]].append((float(edge["cost"]), edge["b"]))
        graph[edge["b"]].append((float(edge["cost"]), edge["a"]))
    queue = [(0.0, (source,), source)]
    visited = set()
    while queue:
        cost, route, node = heapq.heappop(queue)
        if node in visited:
            continue
        if node == destination:
            return {"path": list(route), "total_cost": round(cost, 2), "reachable": True}
        visited.add(node)
        for weight, neighbor in sorted(graph[node]):
            if neighbor not in visited:
                heapq.heappush(queue, (cost + weight, route + (neighbor,), neighbor))
    return {"path": [], "total_cost": None, "reachable": False}

def scenario(topology=None, source="BKK-CORE-1", destination="RYG-EDGE-1", failure=("CBI-AGG-1", "RYG-EDGE-1")):
    topology = topology or DEFAULT_TOPOLOGY
    before = shortest_path(topology, source, destination)
    after = shortest_path(topology, source, destination, [failure])
    return {"scenario": "single-link-failure", "source": source, "destination": destination,
            "failed_link": list(failure), "before": before, "after": after,
            "interpretation": "Shortest path recomputed using abstract link costs; not BGP/OSPF convergence or measured failover time."}

def synthetic_logs(topology=None):
    """Fictional sample events for testing; timestamps and device IDs are invented."""
    topology = topology or DEFAULT_TOPOLOGY
    vendor = {n["id"]: n["vendor"] for n in topology["nodes"]}
    initial = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)
    entries = [
        (0, "CBI-AGG-1", "MAJOR", "LINK_DOWN", "GE0/0/2", "Physical interface link down"),
        (1, "RYG-EDGE-1", "MAJOR", "LINK_DOWN", "GE0/1/0", "Peer-facing interface down"),
        (2, "CBI-AGG-1", "MAJOR", "LINK_DOWN", "GE0/0/2", "Repeat alarm from interface"),
        (3, "BKK-CORE-1", "WARNING", "ROUTE_CHANGE", "Eth1/1", "Alternative route selected in graph model"),
        (4, "BKK-CORE-2", "INFO", "ROUTE_CHANGE", "xe-0/0/1", "Transit path active"),
        (6, "AYA-AGG-1", "WARNING", "HIGH_UTILIZATION", "1/1/2", "Simulated link utilization 81 pct"),
        (8, "CBI-AGG-1", "MAJOR", "LINK_DOWN", "GE0/0/2", "Repeat alarm while down"),
        (10, "RYG-EDGE-1", "INFO", "ROUTE_CHANGE", "GE0/1/1", "Receiving via backup path"),
        (12, "AYA-AGG-1", "MINOR", "OPTICAL_WARNING", "1/1/2", "Fictional receive-power warning"),
        (15, "CBI-AGG-1", "INFO", "LINK_UP", "GE0/0/2", "Interface restored"),
        (16, "RYG-EDGE-1", "INFO", "LINK_UP", "GE0/1/0", "Peer-facing interface restored"),
        (17, "BKK-CORE-1", "INFO", "ROUTE_CHANGE", "Eth1/1", "Normal route restored in graph model"),
        (25, "BKK-CORE-2", "MINOR", "CPU_WARNING", "xe-0/0/0", "Temporary CPU threshold notice"),
        (27, "BKK-CORE-2", "INFO", "CPU_NORMAL", "xe-0/0/0", "CPU threshold normal"),
    ]
    lines = []
    for mins, router, severity, code, interface, message in entries:
        ts = (initial + timedelta(minutes=mins)).strftime('%Y-%m-%dT%H:%M:%SZ')
        lines.append(f'{ts} router={router} vendor={vendor[router]} severity={severity} code={code} interface={interface} message="{message}"')
    return lines

def make_svg(topology, report, output):
    """SVG for presentation, arrows not tied to real routing protocols."""
    positions = {'BKK-CORE-1': (85, 110), 'BKK-CORE-2': (270, 45), 'CBI-AGG-1': (270, 170),
                 'AYA-AGG-1': (470, 45), 'RYG-EDGE-1': (660, 110)}
    before = {frozenset((a, b)) for a, b in zip(report['before']['path'], report['before']['path'][1:])}
    after = {frozenset((a, b)) for a, b in zip(report['after']['path'], report['after']['path'][1:])}
    failed = frozenset(report['failed_link'])
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="250" viewBox="0 0 760 250">',
           '<rect width="760" height="250" rx="14" fill="#F5F8FC"/>',
           '<text x="30" y="27" fill="#183554" font-family="sans-serif" font-size="16" font-weight="bold">Backbone topology | link failure &amp; alternate path</text>']
    for e in topology['links']:
        a, b = e['a'], e['b']; x1,y1=positions[a]; x2,y2=positions[b]
        pair = frozenset((a,b)); color = '#D9534F' if pair == failed else '#008F96' if pair in after else '#A9BAD0'
        dash = ' stroke-dasharray="6 4"' if pair == failed else ''
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="5"{dash}/>')
        svg.append(f'<text x="{(x1+x2)/2 + 4}" y="{(y1+y2)/2-6}" font-size="12" fill="#39485B">{e["cost"]}</text>')
    for node, (x,y) in positions.items():
        svg.extend([f'<rect x="{x-68}" y="{y-21}" width="136" height="42" rx="8" fill="#173754"/>',
                    f'<text x="{x}" y="{y+5}" fill="white" text-anchor="middle" font-size="12" font-family="sans-serif">{node}</text>'])
    svg.extend(['<text x="30" y="228" fill="#008F96" font-size="12">Teal: active alternate path</text>',
                '<text x="270" y="228" fill="#D9534F" font-size="12">Red dashed: failed link</text>', '</svg>'])
    Path(output).write_text('\n'.join(svg), encoding='utf-8')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--topology', type=Path, default=Path(__file__).resolve().parents[1] / 'data' / 'topology.json')
    ap.add_argument('--output', type=Path, default=Path('outputs/backbone_result.json'))
    ap.add_argument('--svg', type=Path, default=Path('outputs/backbone_topology.svg'))
    args = ap.parse_args()
    topology = json.loads(args.topology.read_text(encoding='utf-8'))
    report = scenario(topology)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    make_svg(topology, report, args.svg)
    print(f'Before: {" -> ".join(report["before"]["path"])} (cost {report["before"]["total_cost"]})')
    print(f'After : {" -> ".join(report["after"]["path"])} (cost {report["after"]["total_cost"]})')
    print(f'Saved {args.output} and {args.svg}')
if __name__ == '__main__':
    main()
