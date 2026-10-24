import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from backbone import DEFAULT_TOPOLOGY, shortest_path, scenario, synthetic_logs
from log_analyzer import parse_line, analyze_lines
from dashboard import build_dashboard
from run_all import run

class BackboneTests(unittest.TestCase):
    def test_route_before_and_after_link_failure(self):
        result = scenario()
        self.assertEqual(result['before']['path'], ['BKK-CORE-1', 'CBI-AGG-1','RYG-EDGE-1'])
        self.assertEqual(result['before']['total_cost'], 20)
        self.assertEqual(result['after']['path'], ['BKK-CORE-1','BKK-CORE-2','AYA-AGG-1','RYG-EDGE-1'])
        self.assertEqual(result['after']['total_cost'], 38)
    def test_unreachable_when_all_edges_cut(self):
        links = [(e['a'],e['b']) for e in DEFAULT_TOPOLOGY['links']]
        route = shortest_path(DEFAULT_TOPOLOGY, 'BKK-CORE-1','RYG-EDGE-1', links)
        self.assertFalse(route['reachable'])
        self.assertIsNone(route['total_cost'])
    def test_invalid_cost_rejected(self):
        import copy
        topo=copy.deepcopy(DEFAULT_TOPOLOGY);topo['links'][0]['cost']=-1
        with self.assertRaises(ValueError):
            shortest_path(topo,'BKK-CORE-1','RYG-EDGE-1')

class LogTests(unittest.TestCase):
    def test_parses_quoted_message(self):
        event=parse_line(synthetic_logs()[0])
        self.assertEqual(event['severity'], 'MAJOR')
        self.assertEqual(event['message'], 'Physical interface link down')
    def test_invalid_rows_rejected_but_good_rows_retained(self):
        lines = synthetic_logs()+['bad ts router=NOPE', '']
        events, summary, errors = analyze_lines(lines)
        self.assertEqual(len(events),14)
        self.assertEqual(summary['invalid_lines'],1)
        self.assertEqual(len(errors),1)
    def test_repeat_alarm_grouped(self):
        _, summary, _ = analyze_lines(synthetic_logs())
        matches=[c for c in summary['incident_candidates'] if c['router']=='CBI-AGG-1' and c['event_type']=='LINK_DOWN']
        self.assertEqual(matches[0]['occurrences'], 3)

class DashboardTests(unittest.TestCase):
    def test_dashboard_contains_offline_data(self):
        events, summary, _ = analyze_lines(synthetic_logs())
        doc=build_dashboard(events,summary)
        self.assertIn('Network Fault & Alarm Analysis',doc)
        self.assertIn('CBI-AGG-1',doc)
        self.assertNotIn('https://',doc)
    def test_end_to_end_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            report, summary=run(td)
            self.assertEqual(summary['total_events'],14)
            for path in ['data/sample_network.log','data/topology.json','outputs/events.csv','outputs/network_dashboard.html','outputs/backbone_result.json','outputs/backbone_topology.svg']:
                self.assertTrue((Path(td)/path).is_file(),path)
if __name__=='__main__':
    unittest.main()
