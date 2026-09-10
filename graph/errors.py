"""
Errors the road-graph layer raises that callers need to tell apart.

A module of its own, with no imports, so the web layer can catch these without
importing graph_loader — which builds its registry on import and, through
preprocessing.osm_processor, pulls in osmnx: about three seconds and a heavy
dependency the API does not otherwise need until a graph is actually loaded.
"""

from __future__ import annotations


class UnknownGraphError(KeyError):
    """
    A graph name that is not in the registry — the caller's mistake.

    Kept distinct from a KNOWN graph whose file has not been built: that one
    is the server's problem (FileNotFoundError, reported as unavailable). An
    unknown name used to surface as 503 from one endpoint, 500 "an unexpected
    error occurred" from another and 200 from a third, because it was a bare
    KeyError that each caller handled however it happened to.

    Subclasses KeyError because that is what graph_path has always raised, so
    existing `except KeyError` handlers keep working. __str__ is overridden
    because KeyError quotes its message — which is how responses came to read
    "\"Unknown graph 'x'...\"" with the quotes doubled.
    """

    def __init__(self, name: str, known):
        self.name = name
        self.known = sorted(known)
        self.message = f"Unknown graph '{name}'. Known: {', '.join(self.known)}"
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message
