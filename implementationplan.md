# ChainSleuth — corrected implementation plan

Graph Hacks 2026 · Primary track: Agents That Act on Connected Data · FalkorDB-first architecture

The revised plan uses the official FalkorDB documentation, server repository, GraphRAG SDK and integration guides to make ChainSleuth more than a collection of anomaly-detection queries.

The key architectural decision is to use FalkorDB for structured procurement facts and multi-hop investigation, and GraphRAG for contextual evidence retrieval and grounded explanations. The two layers complement each other: GraphRAG supports retrieval from documents and cited answers, while explicit Cypher queries handle numeric reconciliation and anomaly rules.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+2



The entire implementation can be generated and assisted by a coding agent, but the build still needs integration tests, verified query behaviour and a stable demo. I recommend allowing the full four-day event window for the richer implementation, with a functioning end-to-end version completed well before submission closes.

## 1. Product definition

ChainSleuth is an explainable procurement investigation agent that finds suspicious connections between suppliers, invoices, payments and shipments, then builds an evidence-backed investigation that an auditor can inspect.

Its central use case is not “AI detects fraud.” It is:

> A procurement auditor selects an invoice or asks a question. ChainSleuth traces related records through FalkorDB, runs deterministic checks, retrieves relevant supporting documents, and explains which facts justify further review.

## Example investigation

Invoice INV-1043

Supplier A · 100 units billed

Multi-hop supplier relationship

Supplier A → shared account → Supplier B → related invoice

Delivery reconciliation

100 units billed; 60 units recorded as shipped

Result: investigation recommended

The graph returns the related records, the reconciliation rule returns the 40-unit discrepancy, and the agent explains the evidence. This is a synthetic example, not a fraud determination.

The differentiation is the combined investigation: the system joins the relationship evidence and the transaction evidence into one reviewable case, rather than simply producing independent anomaly alerts.

## 2. What the six official resources mean for this project

| Resource                                                           | How ChainSleuth should use it                                                                         |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| [Getting Started](https://docs.falkordb.com/getting-started/)      | Local setup, property-graph modelling, Python client and Cypher query execution.                      |
| [FalkorDB documentation](https://docs.falkordb.com/)               | Core graph capabilities, indexes, graph queries and operational setup.                                |
| [FalkorDB server repository](https://github.com/FalkorDB/FalkorDB) | Server behaviour, releases, Docker deployment and compatibility reference.                            |
| [GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK)           | Typed knowledge graph extraction, retrieval, source provenance and grounded natural-language answers. |
| [GenAI Tools](https://docs.falkordb.com/genai-tools)               | Select suitable integration approaches; avoid adding multiple overlapping agent frameworks.           |
| [Integration guide](https://docs.falkordb.com/integration)         | Official clients, REST integration, bulk CSV loading and optional deployment extensions.              |

FalkorDB documents property graphs, OpenCypher-based querying, full-text and vector indexes, and Python and other official clients. Its integration catalogue includes a bulk loader for larger CSV imports.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+3



The GraphRAG SDK is worth incorporating, but with a defined responsibility. Its current repository documents an asynchronous `GraphRAG` API, schema-constrained extraction, multi-path retrieval and source-context inspection. The repository also shows that v1 differs significantly from older v0 APIs.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+2



Implementation rule: pin a tested release of FalkorDB and the GraphRAG SDK. Do not let a coding agent mix examples from the legacy SDK with current v1 code.

## 3. Architecture

Use one application, one primary graph database, a deterministic detection layer and one agent orchestration layer. Add GraphRAG for the document evidence, not as a replacement for the procurement data model.

\#chatgpt-mermaid-\_r_vh\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_vh\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_vh\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_vh\_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-\_r_vh\_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_vh\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_vh\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_vh\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_vh\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_vh\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_vh\_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_vh\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_vh\_ p{margin:0;}#chatgpt-mermaid-\_r_vh\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .cluster-label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .cluster-label span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_vh\_ .label text,#chatgpt-mermaid-\_r_vh\_ span{fill:rgb(13, 13, 13);color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .node rect,#chatgpt-mermaid-\_r_vh\_ .node circle,#chatgpt-mermaid-\_r_vh\_ .node ellipse,#chatgpt-mermaid-\_r_vh\_ .node polygon,#chatgpt-mermaid-\_r_vh\_ .node path{fill:rgb(250, 232, 222);stroke:rgb(239, 139, 87);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .rough-node .label text,#chatgpt-mermaid-\_r_vh\_ .node .label text,#chatgpt-mermaid-\_r_vh\_ .image-shape .label,#chatgpt-mermaid-\_r_vh\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_vh\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .rough-node .label,#chatgpt-mermaid-\_r_vh\_ .node .label,#chatgpt-mermaid-\_r_vh\_ .image-shape .label,#chatgpt-mermaid-\_r_vh\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_vh\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_vh\_ .root .anchor path{fill:rgb(143, 143, 143)!important;stroke-width:0;stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_vh\_ .arrowheadPath{fill:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_vh\_ .edgePath .path{stroke:rgb(143, 143, 143);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .flowchart-link{stroke:rgb(143, 143, 143);fill:none;}#chatgpt-mermaid-\_r_vh\_ .edgeLabel{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_vh\_ .edgeLabel p{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_vh\_ .edgeLabel rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_vh\_ .labelBkg{background-color:rgba(252, 252, 252, 0.5);}#chatgpt-mermaid-\_r_vh\_ .cluster rect{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .cluster text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ .cluster span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(243, 243, 243);border:1px solid rgba(0, 0, 0, 0.1);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_vh\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_vh\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_vh\_ .icon-shape,#chatgpt-mermaid-\_r_vh\_ .image-shape{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_vh\_ .icon-shape p,#chatgpt-mermaid-\_r_vh\_ .image-shape p{background-color:rgb(252, 252, 252);padding:2px;}#chatgpt-mermaid-\_r_vh\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_vh\_ .image-shape .label rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_vh\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_vh\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_vh\_ .node .neo-node{stroke:rgb(239, 139, 87);}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_vh\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_vh\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node .neo-line path{stroke:rgb(239, 139, 87);filter:none;}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_vh\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_vh\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_vh\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_vh\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_vh\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(109, 46, 15);}#chatgpt-mermaid-\_r_vh\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(109, 46, 15);}#chatgpt-mermaid-\_r_vh\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_vh\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_vh\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(255, 245, 240);stroke:rgb(229, 208, 195);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .node rect,#chatgpt-mermaid-\_r_vh\_ .node circle,#chatgpt-mermaid-\_r_vh\_ .node ellipse,#chatgpt-mermaid-\_r_vh\_ .node polygon,#chatgpt-mermaid-\_r_vh\_ .node path{fill:rgb(255, 231, 217);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_vh\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_vh\_ .node.mermaid-decision .label-container{fill:rgb(255, 245, 240);stroke:rgb(229, 208, 195);stroke-dasharray:2,2;}#chatgpt-mermaid-\_r_vh\_ .edgePaths .flowchart-link{stroke:rgb(143, 143, 143);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_vh\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_vh\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}Auditor UIFastAPI applicationInvestigation orchestratorDeterministic detection engineReviewed Cypher query toolsFalkorDBGraphRAG evidence retrievalPublic and syntheticdocumentsDocument ingestionConnected records and pathsSource document contextEvidence assembly and scoringLLM explanation and next-steprecommendationInvestigation caseFindings and evidence UI

### Components and boundaries

FastAPI: serves the UI's API, validates requests and exposes health and investigation endpoints.

Detection engine: runs fixed, tested Cypher queries and deterministic calculations. The LLM does not replace the rules.

GraphRAG SDK: retrieves supporting information from policy documents, supplier procedure documents, purchase specifications and incident notes. It can also return retrieval context to help the app ground explanations in their sources.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+1



Investigation orchestrator: decides which investigation tools to invoke, assembles their structured outputs and controls the report lifecycle.

FalkorDB: stores the operational graph, its relationships, and persistent investigation findings. It is not just the display layer.

### Why not use every FalkorDB GenAI integration?

The official GenAI catalogue includes LangChain, LangGraph, AG2, LlamaIndex, an MCP server and GraphRAG SDK.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+1



Using all of them would create integration work without improving the central demo. Use GraphRAG SDK and direct Python client queries first. Add an MCP endpoint or LangGraph workflow only when it solves a specific integration problem, not just to increase the technology count.

## 4. Corrected FalkorDB data model

The procurement graph should be authoritative for structured facts. GraphRAG can connect extracted document knowledge to those facts, but it must not silently overwrite transaction data with LLM-extracted guesses.

### Operational node types

| Node             | Required properties                                                         |
| ---------------- | --------------------------------------------------------------------------- |
| `Supplier`       | `supplier_id`, `name`, `status`, `created_at`                               |
| `BankAccount`    | `account_ref`, `bank_code`, `account_status`                                |
| `Owner`          | `owner_id`, `name`                                                          |
| `Invoice`        | `invoice_id`, `fingerprint`, `amount`, `currency`, `invoice_date`, `status` |
| `InvoiceLine`    | `line_id`, `quantity`, `unit`, `unit_price`                                 |
| `PurchaseOrder`  | `po_id`, `ordered_at`, `status`                                             |
| `Shipment`       | `shipment_id`, `status`, `shipped_at`                                       |
| `ShipmentLine`   | `shipment_line_id`, `quantity`, `unit`                                      |
| `Warehouse`      | `warehouse_id`, `name`, `region`                                            |
| `Payment`        | `payment_id`, `amount`, `currency`, `paid_at`, `status`                     |
| `Product`        | `product_id`, `name`, `unit`                                                |
| `PolicyDocument` | `document_id`, `title`, `document_type`, `version`, `source_uri`            |
| `EvidenceChunk`  | `chunk_id`, `text`, `document_id`, `page_or_section`                        |
| `Finding`        | `finding_id`, `rule_id`, `score`, `severity`, `status`, `created_at`        |
| `Investigation`  | `investigation_id`, `question`, `status`, `created_at`                      |

The additional line-level nodes address a weakness in the original design. Real invoices and shipments may contain several products, multiple quantities and partial deliveries. Comparing only a total quantity at the purchase-order level can produce misleading results.

### Relationship definitions

```

(Supplier)-[:USES_ACCOUNT]->(BankAccount)
(Supplier)-[:CONTROLLED_BY]->(Owner)
(Supplier)-[:SUBMITTED]->(Invoice)

(Invoice)-[:HAS_LINE]->(InvoiceLine)
(InvoiceLine)-[:BILLS_PRODUCT]->(Product)
(Invoice)-[:BILLS]->(PurchaseOrder)

(PurchaseOrder)-[:HAS_LINE]->(POLine)
(POLine)-[:ORDERS_PRODUCT]->(Product)
(PurchaseOrder)-[:FULFILLED_BY]->(Shipment)

(Shipment)-[:HAS_LINE]->(ShipmentLine)
(ShipmentLine)-[:SHIPS_PRODUCT]->(Product)
(Shipment)-[:ROUTE_STOP {sequence: 1}]->(Warehouse)
(Warehouse)-[:APPROVED_NEXT]->(Warehouse)

(Invoice)-[:SETTLED_BY]->(Payment)
(Payment)-[:PAID_TO]->(Supplier)

(PolicyDocument)-[:HAS_CHUNK]->(EvidenceChunk)
(EvidenceChunk)-[:MENTIONS]->(Supplier)
(EvidenceChunk)-[:MENTIONS]->(PurchaseOrder)
(EvidenceChunk)-[:MENTIONS]->(Product)

(Finding)-[:INVOLVES]->(Supplier)
(Finding)-[:INVOLVES]->(Invoice)
(Finding)-[:INVOLVES]->(Shipment)
(Finding)-[:SUPPORTED_BY]->(EvidenceChunk)
(Investigation)-[:CONTAINS]->(Finding)

```

`POLine` needs to be defined as a node if you use the purchase-order line relationships above. It should carry `po_line_id`, `quantity`, `unit`, and `unit_price`.

That makes product-level reconciliation possible:

- Invoice line → billed product and quantity.
- Purchase-order line → ordered product and quantity.
- Shipment line → shipped product and quantity.
- Evidence chunks → the policy or specification relevant to that product.

The important graph pattern is now more useful than a simple supplier-to-account connection:

`Invoice → Supplier → BankAccount ← Supplier ← Invoice`

and:

`Invoice → InvoiceLine → Product ← ShipmentLine ← Shipment`

The first pattern reveals connected supplier networks. The second relates billed items to shipment evidence. These are meaningful traversals, rather than a graph drawn over unrelated tables.

### Data provenance rule

For each extracted document fact, retain its source document and chunk. For each transaction fact, retain its original record ID and source file. The graph should distinguish:

- Observed facts: values loaded from the synthetic transaction dataset.
- Extracted claims: information found in text documents.
- Derived signals: discrepancies and graph relationships calculated by rules.
- Reviewer decisions: human confirmation, dismissal or request for additional evidence.

This distinction is central to making the explanation defensible.

## 5. Core detection rules and Cypher

Build four detection rules, but implement and test them in the order shown below.

### Rule 1 — Connected supplier investigation

Find other suppliers reachable through shared payment infrastructure, then retrieve the invoices and relevant transactions of the connected suppliers.

```
MATCH
  (s1:Supplier)-[:USES_ACCOUNT]->(a:BankAccount)
             <-[:USES_ACCOUNT]-(s2:Supplier)
WHERE s1.supplier_id < s2.supplier_id
RETURN
  s1.supplier_id AS supplier_a,
  s2.supplier_id AS supplier_b,
  a.account_ref AS shared_account
LIMIT 100
```

This is a practical first test because the pattern is simple and the result is easy to verify manually. Expand it in a separate query to return associated invoices, payments and any documented ownership relationships.

Do not treat shared banking infrastructure alone as fraud. It is a reason to review relationships.

### Rule 2 — Duplicate invoices

Calculate a normalized fingerprint in Python during ingestion. Use stable identifiers rather than relying on approximate LLM interpretation.

```
MATCH
  (s1:Supplier)-[:SUBMITTED]->(i1:Invoice),
  (s2:Supplier)-[:SUBMITTED]->(i2:Invoice)
WHERE
  i1.fingerprint = i2.fingerprint
  AND i1.invoice_id < i2.invoice_id
  AND s1.supplier_id <> s2.supplier_id
RETURN
  i1.invoice_id AS invoice_a,
  i2.invoice_id AS invoice_b,
  s1.supplier_id AS supplier_a,
  s2.supplier_id AS supplier_b,
  i1.fingerprint AS fingerprint
```

Use exact duplicates as the initial detection. Near-duplicate invoice detection should be added as a separate, explicitly evaluated capability; otherwise it can introduce false positives from legitimate recurring orders.

### Rule 3 — Invoice, purchase order and delivery reconciliation

Run deterministic calculations in Python after retrieving the corresponding graph records. This makes the unit-conversion logic and exception handling easier to test.

The query retrieves relevant entities:

```
MATCH
  (s:Supplier)-[:SUBMITTED]->(i:Invoice)
  -[:BILLS]->(po:PurchaseOrder)
OPTIONAL MATCH
  (po)-[:FULFILLED_BY]->(sh:Shipment)
RETURN
  s.supplier_id AS supplier_id,
  i.invoice_id AS invoice_id,
  po.po_id AS po_id,
  i.currency AS currency,
  sh.shipment_id AS shipment_id,
  sh.status AS shipment_status
```

Then perform the line-level comparison using the corresponding invoice, order and shipment lines. Compare only matching products and compatible units. Exclude cancelled shipments and account for partial deliveries.

The rule output must distinguish:

- `quantity_mismatch`
- `missing_shipment_evidence`
- `unit_mismatch`
- `unresolved_purchase_order_link`

Those categories are more useful than converting every missing record into a fraud score.

### Rule 4 — Route anomaly

Keep route analysis as a core capability only after the first three rules are stable. Represent approved transitions explicitly and compare them with the ordered stops stored on each shipment.

The output must identify the exact origin, destination, shipment and sequence number of an unapproved transition. Validate the query on the pinned FalkorDB server release before depending on its output in the demo.

### Query execution requirements

FalkorDB's getting-started guide documents the Python client pattern using `FalkorDB`, `select_graph()`, `query()` and `ro_query()`.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+1



Use the official Python client for graph operations. Expose named query functions with validated inputs, not a public endpoint that accepts arbitrary Cypher. For read-only investigations, use the read-only query interface where supported.

Add automated integration tests to verify every query against the exact database image you intend to submit.

## 6. GraphRAG integration: where it belongs

This is the main addition to the original plan after reviewing the SDK.

FalkorDB GraphRAG SDK supports document ingestion, a schema or ontology that guides extraction, graph-based retrieval, and generated answers with inspectable retrieval context. Its documented v1 interface is asynchronous.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+2



Use it for context that cannot be expressed as structured transaction fields alone.

### What documents should be in the graph?

Generate safe synthetic documents for the demo:

- Procurement policy with invoice approval and tolerance rules.
- Product delivery specification.
- Supplier onboarding checklist.
- Warehouse routing policy.
- A short report describing an earlier, synthetic procurement incident.

The structured supplier and transaction graph remains authoritative. GraphRAG adds document-derived relationships and source references.

### Example question

> Why should INV-1043 be investigated, and which procurement policy supports the recommendation?

The workflow should:

1. Use Cypher to find the shared supplier account and the invoice/shipment discrepancy.
2. Retrieve the policy documents relevant to the supplier, product and discrepancy.
3. Assemble the transaction evidence and document context.
4. Generate a response that cites the source records and relevant document passages.
5. Abstain from making a definitive claim if required evidence is missing.

The answer should be able to say:

> INV-1043 is flagged because it bills 100 units while the linked shipment records account for 60 units. The supplier also shares a payment account with Supplier B. The procurement policy document specifies the applicable quantity reconciliation procedure. These are review signals; they do not by themselves establish fraud.

The numeric values come from graph records and deterministic calculations. The policy statement comes from the retrieved document. The LLM combines them but cannot invent either.

### Important: do not use GraphRAG to ingest every CSV row as prose

Transaction rows already have typed fields and known relationships. Loading them as natural-language documents and asking an LLM to extract all their facts introduces unnecessary extraction ambiguity.

Use explicit CSV-to-graph ingestion for structured transaction data, and GraphRAG for the document evidence layer. This is an architectural recommendation based on the distinct capabilities shown in the official getting-started and GraphRAG SDK materials.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+1



### SDK version gate

Before building the full integration, require the coding agent to demonstrate all of the following in a standalone test:

- Install a pinned GraphRAG SDK release.
- Connect it to the same FalkorDB instance.
- Ingest one synthetic policy document using an explicit ontology.
- Finalize or complete the ingestion using the pinned API.
- Retrieve a question and inspect the supporting context.
- Verify the returned evidence can be associated with the correct source document.

The current repository documents v1-style asynchronous usage such as `async with GraphRAG(...)`, `await rag.ingest(...)`, `await rag.finalize()` and `await rag.completion(...)`.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+1



Do not proceed to the full UI integration until that test passes. If it fails, finish the deterministic evidence engine and use a small, direct document-retrieval adapter for the demo instead. The product still works without the optional GraphRAG layer.

## 7. Risk scoring and persistent investigations

Keep the scoring deterministic and explainable. Do not ask the LLM to invent probabilities.

Start with provisional points for each independent signal:

| Rule                                         | Initial points |
| -------------------------------------------- | -------------- |
| Supplier pair shares a payout account        | 20             |
| Independent corroborating relationship found | 15             |
| Exact duplicate invoice fingerprint          | 30             |
| Quantity mismatch after valid reconciliation | 25             |
| Unapproved warehouse transition              | 15             |

These weights are initial engineering choices, not calibrated fraud probabilities. Use a capped score, documented severity thresholds and deduplication so the same evidence is not counted repeatedly.

### Persist the investigation lifecycle

Model findings as durable graph entities rather than transient chat responses.

```

(Investigation)-[:CONTAINS]->(Finding)
(Finding)-[:INVOLVES]->(Supplier)
(Finding)-[:INVOLVES]->(Invoice)
(Finding)-[:INVOLVES]->(Shipment)
(Finding)-[:SUPPORTED_BY]->(EvidenceChunk)
(Finding)-[:TRIGGERED_BY]->(DetectionRule)
(Finding)-[:RELATED_TO]->(Finding)
(Investigation)-[:FOLLOWED_BY]->(Investigation)

```

Define `DetectionRule` with a stable `rule_id`, version, description and scoring configuration. If rule parameters change, the finding should record the version used to generate it. You can keep the actual query definitions in code and store a rule-version identifier in the graph.

Finding properties should include:

```
finding_id
rule_id
rule_version
score
severity
status
created_at
last_evaluated_at
dataset_version
evidence_summary
```

The system should support these statuses:

`open → needs_review → confirmed / dismissed`

“Confirmed” is a reviewer decision. It must not be assigned automatically just because a risk score is high.

### Persistent agent context

The project can demonstrate cross-session memory without building a separate memory framework. Save the investigation, findings and reviewer actions in the graph. On a subsequent session, retrieve the relevant prior investigation and its connected evidence using graph traversal.

For example, an auditor could ask:

> What did we find about Supplier A yesterday, and what new evidence has appeared since then?

The agent retrieves the earlier investigation and compares it with the current graph. This is a useful bonus, but finish the core investigation flow first.

## 8. Application stack and deployment

Use the smallest stack that integrates the documented capabilities cleanly.

| Layer               | Technology                        |
| ------------------- | --------------------------------- |
| Backend             | Python 3.12 + FastAPI             |
| Operational graph   | FalkorDB                          |
| Graph operations    | Official `falkordb` Python client |
| Document GraphRAG   | Pinned `graphrag-sdk` release     |
| Frontend            | Streamlit                         |
| Synthetic data      | Python + Pandas                   |
| Scoring             | Deterministic Python rules        |
| Tests               | Pytest                            |
| Local orchestration | Docker Compose                    |

FalkorDB's getting-started guide documents a Docker deployment exposing server port 6379 and Browser port 3000, and describes authentication configuration.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+1



A development command:

```
docker run --rm \
  -p 6379:6379 \
  -p 3000:3000 \
  -v ./data/falkordb:/var/lib/falkordb/data \
  falkordb/falkordb:latest
```

For submission, replace `latest` with an explicitly tested image version and keep the chosen persistent-volume layout consistent with that image. The official server repository also shows the Docker Browser setup and a volume-mounted quick-start example.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+1



Use an environment file for model credentials and database settings. Do not bake secrets into the repository or expose an unauthenticated database port on a public deployment.

### Recommended repository structure

```
chainsleuth/
├── app/
│   ├── api/
│   │   ├── routes_health.py
│   │   ├── routes_findings.py
│   │   └── routes_investigations.py
│   ├── graph/
│   │   ├── client.py
│   │   ├── schema.py
│   │   ├── ingest_structured.py
│   │   └── repository.py
│   ├── detection/
│   │   ├── supplier_network.py
│   │   ├── duplicate_invoice.py
│   │   ├── reconcile_lines.py
│   │   └── route_anomaly.py
│   ├── graphrag/
│   │   ├── client.py
│   │   ├── ontology.py
│   │   └── ingest_documents.py
│   ├── agent/
│   │   ├── tools.py
│   │   └── orchestrator.py
│   ├── investigations/
│   │   ├── service.py
│   │   └── evidence.py
│   └── scoring.py
├── queries/
│   ├── shared_accounts.cypher
│   ├── duplicate_invoices.cypher
│   ├── invoice_order_shipment.cypher
│   └── route_deviation.cypher
├── data/
│   ├── generate_demo_data.py
│   ├── ground_truth.csv
│   └── policies/
├── tests/
│   ├── test_graph_queries.py
│   ├── test_reconciliation.py
│   ├── test_detection.py
│   ├── test_graphrag.py
│   └── test_end_to_end.py
├── ui/
│   └── streamlit_app.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
└── AI_USAGE.md
```

This structure is deliberately modular: if GraphRAG SDK integration becomes problematic, `detection/`, `investigations/` and the UI can still provide a working product.

## 9. Synthetic data and evaluation

The project should be evaluated against known expected results, not merely on how convincing the generated explanations sound.

Generate structured transaction data plus a small set of synthetic supporting documents. Aim initially for roughly 80 suppliers, 150 purchase orders, 250 invoices, 120 shipments, 60 bank accounts and 10 warehouses. The numbers are adjustable; graph integrity and test coverage matter more.

Create separate ground-truth labels for:

1. A supplier network with a shared payout account and independent corroborating evidence.
2. Exact duplicate invoices associated with different supplier records.
3. An invoice whose billed quantities differ from the sum of valid matching shipment lines.
4. A shipment containing a route transition not present in the approved route network.

Also create legitimate shared-account and partial-shipment cases to test false positives.

Do not load evaluation labels into the operational graph, and do not provide them to the agent as queryable context. Keep them in `data/ground_truth.csv` for tests.

### Metrics to publish

| Metric                  | How to calculate it                                                        |
| ----------------------- | -------------------------------------------------------------------------- |
| Detection recall        | Expected anomalies detected ÷ all planted anomalies                        |
| Precision               | Correctly detected planted anomalies ÷ all positive findings               |
| Reconciliation accuracy | Quantity comparisons that match expected results ÷ tested comparisons      |
| Evidence completeness   | Findings with all expected source IDs and paths ÷ total findings           |
| Grounding accuracy      | Audited explanation claims supported by returned evidence ÷ claims checked |
| Repeatability           | Whether repeated runs on unchanged data create duplicate findings          |
| Query latency           | Local time for each detection query and complete investigation             |

For a hackathon demo, report measurements from your actual test set and machine. Don't claim production-grade detection rates from a small synthetic dataset.

### The no-graph comparison

Build one lightweight baseline that reads the CSV files and performs direct invoice and quantity checks without traversing relationships. Compare it with the graph-based workflow on the supplier-network cases.

Do not intentionally weaken the baseline. The point is to demonstrate what the graph makes easier to express and investigate, not to pretend relational systems cannot detect fraud.

FalkorDB's documentation identifies traversal, full-text and vector search, and graph algorithms as part of its core capabilities. Those are the relevant technical features to demonstrate here.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+1



## 10. Four-day execution plan with scope gates

The event window is approximately 96 hours. Use four days, but aim to have the complete core demo working by the end of Day 2. The remaining time becomes integration, evaluation and polish rather than a last-minute attempt to make the application work.

Day 1

FalkorDB foundation

Start the pinned database image, establish the Python connection, generate synthetic data, implement structured ingestion and build the initial schema. Validate the shared-account query and create the first automated integration test.

Gate: fresh setup successfully loads data and returns the expected supplier connection.

Day 2

Detection engine and working investigation

Implement invoice matching, line-level reconciliation, deterministic scoring, persistent `Finding` nodes, evidence paths and the first investigation UI. Connect the agent to named tools and complete a full investigation without GraphRAG.

Gate: one end-to-end scenario works from input to persisted finding to readable explanation.

Day 3

GraphRAG, source grounding and memory

Run the isolated SDK compatibility test, ingest synthetic procurement policies, retrieve contextual evidence and expose prior investigations as graph-backed context. Add route analysis if the core tests are stable.

Gate: every policy claim displayed in an explanation can be traced to a retrieved source.

Day 4

Evaluation and submission

Test from a clean environment, fix failed queries and dependency issues, complete the README and graph model documentation, record the demo video and verify the live deployment or complete local setup.

Gate: another developer can start the project using the README and reproduce the showcased findings.

This is a priority-based schedule, not a claim that each step requires exactly one day. If a critical test fails, postpone the stretch features rather than compressing testing.

## 11. Coding-agent execution protocol

Because you're using a coding agent for the implementation, give it a controlled sequence of deliverables instead of asking it to generate the entire repository at once.

Use the following instructions as the project's implementation contract.

# ChainSleuth Implementation Contract

Build ChainSleuth, an explainable supply-chain anomaly investigation agent for Graph Hacks 2026. FalkorDB must be the primary graph database and must perform the relationship traversals used by the detection engine.

## Mandatory rules

1. Read the current official FalkorDB documentation, the official FalkorDB server repository, and the current GraphRAG SDK documentation before using their APIs.
2. Pin the FalkorDB server image, Python client, GraphRAG SDK, and application dependencies to tested versions. Do not mix legacy GraphRAG SDK examples with the current API.
3. Use explicit CSV-to-graph ingestion for structured procurement data. Use GraphRAG for synthetic policy and supporting documents, not to infer authoritative transaction values.
4. Use reviewed, named Cypher query functions for all detection operations. Do not execute unrestricted LLM-generated Cypher.
5. Use deterministic arithmetic and scoring. Every generated explanation must be supported by retrieved graph records and source context.
6. Persist findings, relationships, rule versions and reviewer decisions in FalkorDB.
7. Never describe a risk signal as proof of fraud. The product recommends human review and does not autonomously block payments.
8. Use only synthetic, public, or otherwise permitted data. Keep evaluation labels outside the operational graph.
9. Test the product against the exact pinned database and SDK versions.
10. Document AI coding assistance and ensure the final code can be explained by the project team.

## Required implementation order

Phase A: Verify the local FalkorDB connection and create a minimal graph. Run a real Cypher query and prove the result with an automated test.

Phase B: Generate synthetic suppliers, bank accounts, invoices, invoice lines, purchase orders, purchase-order lines, shipments, shipment lines, products and warehouses. Ingest them into FalkorDB and validate graph integrity.

Phase C: Implement shared supplier account detection, exact duplicate invoice detection and product-level invoice/order/shipment reconciliation. Add route validation after these three work.

Phase D: Implement deterministic scoring, evidence assembly and persistent findings. A finding must include its triggering rule, rule version, record IDs, relevant values and reproducible evidence paths.

Phase E: Build a functional investigation UI and an agent that invokes validated tools. Complete an end-to-end investigation before beginning optional features.

Phase F: Integrate a pinned GraphRAG SDK release for synthetic procurement documents. First pass an isolated document-ingestion and evidence-retrieval test, then integrate it with the investigation orchestrator. If the SDK fails the gate, preserve a functioning core and use a limited direct document-retrieval fallback.

Phase G: Add cross-session investigation retrieval, reviewer actions and optional route analysis. Avoid unnecessary multi-agent frameworks or additional databases.

Phase H: Add automated tests for planted anomalies, legitimate shared accounts, missing records, partial shipments, repeated detection runs and unsupported explanation claims. Report measured results rather than assumed performance.

Phase I: Complete documentation, deployment or local instructions, demo video and hackathon submission fields.

## Required final acceptance test

Starting from a clean environment, the application must:

1. Start FalkorDB and connect through the official Python client.
2. Load the synthetic dataset and validate the expected entities and relationships.
3. Detect a planted shared-account supplier network.
4. Detect an exact duplicate invoice and a product-level delivery mismatch.
5. Create and persist an investigation with deterministic scores and evidence paths.
6. Generate an explanation tied to those records without inventing IDs or quantities.
7. Retrieve the relevant synthetic policy evidence through GraphRAG, or clearly report that document evidence is unavailable.
8. Reopen the investigation in a new session and preserve reviewer state.
9. Pass the project's automated tests.
10. Run according to the public README.

Implement the smallest complete solution first. Never sacrifice the working end-to-end investigation to add an untested feature.

## 12. Final submission checklist

The implementation is complete only when all the following are true:

- FalkorDB is central to the operational graph and detection queries.
- The graph model, relationship directions and node properties are documented.
- Three core detection patterns work and are tested.
- Findings persist and contain reproducible evidence.
- The agent uses controlled tools and grounded explanations.
- GraphRAG document retrieval passes its compatibility and grounding tests, or the documented fallback works.
- The UI demonstrates an investigation from start to finish.
- The README documents setup, configuration, data ingestion, graph model and Cypher queries.
- The demo demonstrates both an anomaly and a normal or ambiguous case.
- The repository is public, the deployment or local setup works, and AI assistance is disclosed.
- The submission names Agents That Act on Connected Data as the primary track.

Final recommendation: build the graph-backed investigation engine first, then add GraphRAG for source-grounded procurement policy evidence and persistent investigation context. This delivers a defensible graph-native project while leaving room for a more ambitious agent experience. The official docs support this division of responsibilities, but the exact pinned SDK/server combination and all production queries must still pass your integration tests.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.falkordb.com\&sz=32)

FalkorDB Docs

+3
