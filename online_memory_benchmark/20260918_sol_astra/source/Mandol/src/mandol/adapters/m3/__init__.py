"""M3 interchange, graph construction, and retrieval adapter."""

from importlib import import_module

_EXPORTS = {
    "M3MandolAdapter": (".adapter", "M3MandolAdapter"),
    "M3MandolConfig": (".adapter", "M3MandolConfig"),
    "M3MandolRetriever": (".retriever", "M3MandolRetriever"),
    "OpenAICompatible302EmbeddingAdapter": (
        ".embedding",
        "OpenAICompatible302EmbeddingAdapter",
    ),
    "load_interchange": (".schema", "load_interchange"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "M3MandolAdapter",
    "M3MandolConfig",
    "M3MandolRetriever",
    "OpenAICompatible302EmbeddingAdapter",
    "load_interchange",
]
