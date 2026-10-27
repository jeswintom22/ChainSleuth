import os

# Tests run against an isolated graph on the same pinned FalkorDB server so they never touch demo data.
os.environ["CHAINSLEUTH_GRAPH"] = "chainsleuth_test"
TEST_TOKENS = {"auditor.a": "test-reviewer-token-aaaa", "admin.t": "test-admin-token-bbbbbb"}
os.environ["CHAINSLEUTH_API_USERS"] = (f"auditor.a:reviewer:{TEST_TOKENS['auditor.a']},"
                                       f"admin.t:admin:{TEST_TOKENS['admin.t']}")

import csv  # noqa: E402

import pytest  # noqa: E402

from app.config import BACKEND_DIR  # noqa: E402
from app.graph.ingest import load_dataset, reset_operational_graph  # noqa: E402


@pytest.fixture(scope="session")
def loaded_graph():
    """Fresh graph loaded from the synthetic CSVs once per test session."""
    from data.generate_synthetic import generate

    generate()
    reset_operational_graph()
    counts = load_dataset()
    yield counts
    reset_operational_graph()


@pytest.fixture(scope="module")
def clean_investigation_layer(loaded_graph):
    """Remove findings/investigations/reviews from the TEST graph so each module starts from scratch."""
    from app.graph.client import write

    write("""MATCH (n) WHERE n:Finding OR n:Investigation OR n:ReviewAction OR n:DetectionRun OR n:DetectionRule
                         OR n:EvidenceChunk OR n:AgentTurn
             DETACH DELETE n""")
    yield


@pytest.fixture(scope="session")
def ground_truth():
    with open(BACKEND_DIR / "data" / "ground_truth.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
