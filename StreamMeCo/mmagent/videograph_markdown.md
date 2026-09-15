# Export a readable VideoGraph

```bash
python StreamMeCo/mmagent/videograph_markdown.py graph.pkl -o memories.md
```

Accepts native M3 checkpoints or exported graph JSON. Uses Python's standard
library; no model runtime is loaded.

The compact Markdown contains:

- One summary of node types and link count.
- Character mappings, with large tables folded away.
- One entry per text node: ID, clip, text, and connected node IDs.
- Voice transcripts and face samples in expandable entries.

All node text is retained. Links show weights only when they differ from 1.
Symmetric edges are shown as shared connections; asymmetric edges retain their
direction and weight. Embeddings, raw metadata, timeline indexes, reverse-mapping
duplicates, and separate edge tables are omitted.

The exporter does not refresh or invent character mappings. An absent attribute
in a native checkpoint is distinguished from an empty mapping and from a mapping
unavailable in a reduced JSON export. Original files remain unchanged.

For use in Python, put the module directory on your import path:

```python
from pathlib import Path
from videograph_markdown import render_graph

output = Path("memories.md")
output.write_text("\n".join(render_graph(video_graph, output=output)))
```

Native face images are extracted unchanged beside the Markdown in a `.assets`
folder. The restricted pickle reader accepts current M3 VideoGraph classes with
ordinary Python containers and rejects unsupported serialized classes.

The Jake DAY1 result renderer and replay exporter use this compact format.
