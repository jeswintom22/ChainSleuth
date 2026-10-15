import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = dotenv_values(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _api_key() -> str | None:
    # A key in backend/.env wins over the shell environment; obvious placeholders count as "not set".
    key = (_ENV_FILE.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    return None if not key or "your" in key.lower() or key.endswith("...") else key


@dataclass(frozen=True)
class Settings:
    falkordb_host: str = os.getenv("FALKORDB_HOST", "localhost")
    falkordb_port: int = int(os.getenv("FALKORDB_PORT", "6379"))
    falkordb_password: str | None = os.getenv("FALKORDB_PASSWORD") or None
    graph_name: str = os.getenv("CHAINSLEUTH_GRAPH", "chainsleuth")
    docs_graph_name: str = os.getenv("CHAINSLEUTH_DOCS_GRAPH", "chainsleuth_docs")
    openai_api_key: str | None = _api_key()
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-4.1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-large")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "256"))
    data_dir: Path = BACKEND_DIR / "data" / "generated"
    policies_dir: Path = BACKEND_DIR / "data" / "policies"
    dataset_version: str = os.getenv("DATASET_VERSION", "synthetic-v1")


settings = Settings()

# The exact server the product is tested against (docker-compose.yml) and its GRAPH module version.
FALKORDB_IMAGE = "falkordb/falkordb:v4.22.0"
EXPECTED_MODULE_VERSION = "42200"
