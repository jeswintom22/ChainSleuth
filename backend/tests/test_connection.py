"""Phase A gate: real FalkorDB connection, minimal graph, real Cypher query."""
from app.graph.client import get_db, read, write


def test_ping():
    assert get_db().connection.ping()


def test_minimal_shared_account_graph():
    g = get_db().select_graph("chainsleuth_test_phase_a")
    try:
        write(
            """
            CREATE (s1:Supplier {supplier_id: 'S1'}), (s2:Supplier {supplier_id: 'S2'}),
                   (a:BankAccount {account_ref: 'ACC-1'}),
                   (s1)-[:USES_ACCOUNT]->(a), (s2)-[:USES_ACCOUNT]->(a)
            """,
            graph=g,
        )
        result = read(
            """
            MATCH (s1:Supplier)-[:USES_ACCOUNT]->(a:BankAccount)<-[:USES_ACCOUNT]-(s2:Supplier)
            WHERE s1.supplier_id < s2.supplier_id
            RETURN s1.supplier_id AS a, s2.supplier_id AS b, a.account_ref AS acct
            """,
            graph=g,
        )
        assert result == [{"a": "S1", "b": "S2", "acct": "ACC-1"}]
    finally:
        g.delete()
