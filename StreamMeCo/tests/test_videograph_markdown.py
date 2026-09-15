"""Check information preservation and source-state distinctions in graph exports."""
import base64
import importlib.util
from pathlib import Path
import pickle
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'mmagent/videograph_markdown.py'
spec = importlib.util.spec_from_file_location('videograph_markdown', MODULE)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class GraphExportTests(unittest.TestCase):
    def graph(self):
        return {
            'nodes': [
                {'id': 0, 'type': 'voice', 'embeddings': [[123456.7]],
                 'metadata': {'contents': ['first <voice_0>', 'second\nline'], 'custom': 'kept'}},
                {'id': 1, 'type': 'semantic', 'embedding_count': 17,
                 'metadata': {'contents': ['identity claim'], 'timestamp': 1}},
                {'id': 2, 'type': 'episodic', 'metadata': {'contents': []}},
            ],
            'edges': [{'source': 0, 'target': 1, 'weight': 0.7},
                      {'source': 1, 'target': 0, 'weight': 0.2},
                      {'source': 0, 'target': 0, 'weight': 1}],
            'edge_storage': 'directed', 'state_complete': True,
            'graph_attributes': {'text_nodes': [1, 2], 'text_nodes_by_clip': {1: [2, 1]},
                                 'character_mappings': {}},
        }

    def test_contents_edges_and_absent_empty_distinction(self):
        graph = self.graph()
        before = pickle.dumps(graph)
        text = '\n'.join(exporter.render_graph(graph))
        self.assertIn('first &lt;voice_0&gt;', text)
        self.assertIn('second<br>line', text)
        self.assertNotIn('"custom": "kept"', text)
        self.assertIn('Empty — no character mappings stored.', text)
        self.assertIn('→ [1](#video-graph-node-1) (weight 0.7)', text)
        self.assertIn('← [1](#video-graph-node-1) (weight 0.2)', text)
        self.assertNotIn('text_nodes_by_clip', text)
        self.assertIn('**2**: (no text)', text)
        self.assertNotIn('embedding_count', text)
        self.assertNotIn('123456.7', text)
        self.assertEqual(pickle.dumps(graph), before)

    def test_reduced_json_does_not_claim_absent_state(self):
        graph = self.graph()
        del graph['state_complete']
        del graph['graph_attributes']
        text = '\n'.join(exporter.render_graph(graph))
        self.assertIn('Not included in this JSON export.', text)
        self.assertNotIn('Not stored in this construction checkpoint.', text)

    def test_symmetric_edges_and_character_mapping_are_compact(self):
        graph = self.graph()
        graph['edges'] = [{'source': 0, 'target': 1, 'weight': 1},
                          {'source': 1, 'target': 0, 'weight': 1}]
        graph['graph_attributes']['character_mappings'] = {'character_0': ['voice_0']}
        text = '\n'.join(exporter.render_graph(graph))
        self.assertIn('3 nodes · 1 links', text)
        self.assertIn('character_0 | [voice_0](#video-graph-node-0)', text)
        self.assertNotIn('Incoming', text)
        self.assertNotIn('Outgoing', text)
        self.assertNotIn('reverse_character_mappings', text)

    def test_face_bytes_exported_unchanged(self):
        data = b'\xff\xd8\xffexample-image-payload'
        graph = {'nodes': [{'id': 9, 'type': 'img', 'metadata': {
            'contents': [base64.b64encode(data).decode()]}}], 'edges': []}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'memory.md'
            text = '\n'.join(exporter.render_graph(graph, output=output))
            self.assertEqual((Path(directory) / 'memory.assets/face_9_1.jpg').read_bytes(), data)
            self.assertIn('memory.assets/face_9_1.jpg', text)

    def test_unknown_pickle_class_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.pkl'
            path.write_bytes(pickle.dumps(Path('anything')))
            with self.assertRaisesRegex(pickle.UnpicklingError, 'Unsupported checkpoint class'):
                exporter.load_graph(path)


if __name__ == '__main__':
    unittest.main()
