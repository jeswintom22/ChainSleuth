# AI coding assistance disclosure

ChainSleuth was built during Graph Hacks 2026 (15–18 October 2026) with help from an AI coding agent: Devin, by Cognition, running Claude in the developer's IDE.

## What the assistant did

- Read the current FalkorDB documentation, the FalkorDB server releases, and the GraphRAG SDK documentation and installed source, then wrote code against the API that was actually installed. One example: the pinned `graphrag-sdk` 1.3.0 exposes `Ontology`, `Entity` and `Relation`, not the newer names used in the docs.
- Generated most of the code (backend, synthetic data generator, frontend, tests) step by step, following the required phase order (A → I) and running the automated tests after each phase.
- Investigated failures against the live server, and documented and tested the results:
  - FalkorDB does not enforce relationship uniqueness within a pattern, so self-matches had to be excluded explicitly.
  - FalkorDB 6.0.2 dropped a `WHERE` clause before a filtered `OPTIONAL MATCH`, so a `WITH` barrier was added.
  - `graphrag-sdk` 1.3.0 uses a full-text index procedure signature that FalkorDB 6.0.x rejects. This led to pinning FalkorDB v4.22.0.
  - The SDK keeps its ontology in a companion graph named `<graph>__ontology`.
  - Windows event-loop teardown noise was fixed by using one long-lived background loop.
- Resolved dependencies with a publication-date cutoff (at least 7 days old), and avoided npm packages published on the day of development.

## What humans did and remain responsible for

- Defined the product, the implementation contract, the architecture decisions and the scope.
- Chose the LLM provider and UI stack, and supplied API credentials locally (never shared with the assistant or committed).
- Review and own the code, and must be able to explain every part of it. The code is organised so that each part can be explained on its own:
  - detection rules are short functions over named Cypher queries;
  - scoring and reconciliation arithmetic are pure functions with unit tests;
  - all LLM output passes a deterministic grounding validator.

## Guardrails applied to AI-generated behaviour at runtime

- The LLM never writes Cypher. It can only call validated, named tools.
- Detection, arithmetic and scoring are deterministic. The LLM only phrases explanations, and only from the evidence pack.
- Generated text that mentions IDs or numbers missing from the evidence, or that uses wording such as "fraud" or "proof", is rejected and replaced by a deterministic explanation.
- Findings are review signals. Only a human reviewer can set a finding to `confirmed`, and the system never approves, holds or releases payments.
