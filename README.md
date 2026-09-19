# M3-streamconative

> Multimodal streaming memory with optional compression and controller-free retrieval.

M3-streamconative builds episodic, semantic, voice, and face memory from video and audio. It supports native M3 retrieval and an adapter to Mandol's hybrid retrieval stack.

## Quick links

- [Project overview and architecture](docs/README.md)
- [Detailed architecture](docs/ARCHITECTURE.md)
- [Mandol adapter contract](docs/mandoladaptor.md)
- [GPU pipeline requirements](docs/GPU_PIPELINE_REQUIREMENTS.md)
- [Hyperstack runbook](docs/HYPERSTACK_GPU_RUNBOOK.md)

## Repository layout

```text
StreamMeCo/   production streaming-memory implementation
Mandol/       hybrid retrieval integration
benchmark/    benchmark datasets and run artifacts
docs/         project documentation and runbooks
consolidation/ identity-consolidation utilities
```

See the [full overview](docs/README.md) for the memory model, retrieval paths, current scope, and documentation index.
