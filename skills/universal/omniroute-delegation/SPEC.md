# OmniRoute Delegation Specification

## 1. Scope

This skill owns only the OmniRoute delegation boundary. External orchestration skills are outside this package's modification boundary.

## 2. Architectural invariants

The implementation MUST provide:

- one security-enforcing `DelegationGateway`;
- strict separation of transport, tool, leaf, and audit contracts;
- typed execution states;
- typed security and semantic exceptions;
- tolerant semantic parsing with provenance;
- preservation of valid partial evidence;
- an explicit L3T interface and a reserved L3W interface.

## 3. Trust boundary

`MCPClient.call_tool` remains responsible for transport-level discovery and JSON Schema validation. The `DelegationGateway` is the only supported delegation facade and performs credential scanning before dispatch.

A future integration MUST NOT introduce a second direct delegation path.

## 4. Semantic result policy

Valid findings and coverage status are independent dimensions.

Examples:

- findings + no raw errors → `SUCCESS`;
- findings + malformed entries → `PARTIAL_COVERAGE`;
- no parseable result after recovery → `SCHEMA_VIOLATION` and `SemanticCoverageFailedError`.

An empty findings list is never sufficient evidence of complete coverage.

## 5. L3T and L3W

L3T delegates are stateless and exchange payloads through the API.

L3W delegates are stateful workers and must eventually receive an isolated workspace and explicit harness. The current refactor defines the interface only; it does not expand the worker runtime.

## 6. Maintenance boundaries

- `SKILL.md`: runtime behavior and routing.
- `SPEC.md`: maintenance and architecture contract.
- `SOURCES.md`: provenance and evidence.
- `references/`: wire schemas and normative protocol material.
- `tests/`: regression and contract evaluation.

