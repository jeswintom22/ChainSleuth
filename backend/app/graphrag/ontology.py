"""Ontology constraining GraphRAG extraction from the synthetic procurement policy documents.

Written against the pinned graphrag-sdk 1.3.0 API (Ontology / Entity / Relation). Document entities
live in a separate FalkorDB graph (settings.docs_graph_name) so extracted claims can never overwrite
the authoritative transaction graph.
"""
from graphrag_sdk import Entity, Ontology, Relation

POLICY_ONTOLOGY = Ontology(
    entities=[
        Entity(label="Policy", description="A named procurement policy, specification, checklist or incident review document"),
        Entity(label="Control", description="A required procurement control or procedure, e.g. three-way match, duplicate invoice check"),
        Entity(label="Threshold", description="A numeric tolerance or limit, e.g. a quantity tolerance percentage"),
        Entity(label="RiskSignal", description="A condition that requires review, e.g. shared payout account, route deviation"),
        Entity(label="Role", description="A team or role responsible for a control, e.g. Vendor Master Data, procurement reviewer"),
        Entity(label="RecordType", description="A type of procurement record, e.g. invoice, purchase order, shipment, bank account"),
    ],
    relations=[
        Relation(label="REQUIRES", description="A policy or control requires a control, action or review",
                 patterns=[("Policy", "Control"), ("Control", "Control"), ("Policy", "Role"), ("Control", "Role"),
                           ("Control", "RecordType"), ("Policy", "RiskSignal")]),
        Relation(label="DEFINES_THRESHOLD", description="A policy or control defines a threshold",
                 patterns=[("Policy", "Threshold"), ("Control", "Threshold")]),
        Relation(label="ADDRESSES", description="A control addresses a risk signal", patterns=[("Control", "RiskSignal")]),
        Relation(label="RESPONSIBLE_FOR", description="A role is responsible for a control or for reviewing a signal",
                 patterns=[("Role", "Control"), ("Role", "RiskSignal"), ("Role", "RecordType")]),
        Relation(label="APPLIES_TO", description="A control or signal applies to a record type",
                 patterns=[("Control", "RecordType"), ("RiskSignal", "RecordType")]),
    ],
)
