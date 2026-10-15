"""FalkorDB connection helpers using the official `falkordb` Python client."""
from functools import lru_cache
from typing import Any

from falkordb import FalkorDB, Graph

from app.config import settings


@lru_cache(maxsize=1)
def get_db() -> FalkorDB:
    return FalkorDB(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        password=settings.falkordb_password,
    )


def get_graph(name: str | None = None) -> Graph:
    return get_db().select_graph(name or settings.graph_name)


def rows(result) -> list[dict[str, Any]]:
    """Convert a falkordb QueryResult into a list of dicts keyed by column alias."""
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in result.header]
    cols = [c.decode() if isinstance(c, bytes) else c for c in cols]
    return [dict(zip(cols, r)) for r in result.result_set]


def read(cypher: str, params: dict | None = None, graph: Graph | None = None) -> list[dict[str, Any]]:
    """Read-only query (GRAPH.RO_QUERY)."""
    return rows((graph or get_graph()).ro_query(cypher, params or {}))


def write(cypher: str, params: dict | None = None, graph: Graph | None = None) -> list[dict[str, Any]]:
    return rows((graph or get_graph()).query(cypher, params or {}))


def ping() -> bool:
    try:
        return bool(get_db().connection.ping())
    except Exception:
        return False
