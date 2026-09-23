from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from .engineering_runner import EngineeringPassResult
from .planner import PreparedAudit
from .security_runner import SecurityPassResult


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _inspection_result(observations: Iterable[object]) -> str:
    states = [getattr(item, "state", "NOT_DETERMINABLE") for item in observations]
    if not states:
        return "NOT_DETERMINABLE"
    if all(state == "NOT_FOUND" for state in states):
        return "NOT_FOUND"
    return "NOT_DETERMINABLE"


def _identity(prepared: PreparedAudit) -> Dict[str, str]:
    project = prepared.snapshot.project_state
    return {
        "repository": project.repository_identity,
        "commit": project.revision_identity,
        "branch": "NOT_DETERMINABLE",
        "version": "NOT_DETERMINABLE",
        "build_version": "NOT_DETERMINABLE",
    }


def render_inventory(prepared: PreparedAudit) -> str:
    identity = _identity(prepared)
    lines = [
        "# INVENTORY AND THREAT MODEL",
        "",
        "## IDENTITY",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Repository | {} |".format(identity["repository"]),
        "| Commit | {} |".format(identity["commit"]),
        "| Branch | {} |".format(identity["branch"]),
        "| Version | {} |".format(identity["version"]),
        "| Build Version | {} |".format(identity["build_version"]),
        "",
        "## INVENTORY",
        "",
        "- Files mapped: {}".format(len(prepared.file_classifications)),
        "- Snapshot fingerprint: {}".format(prepared.snapshot.snapshot_fingerprint),
        "- Working tree state: {}".format(prepared.snapshot.project_state.working_tree_state.value),
        "",
        "## THREAT MODEL",
        "",
        "- Assets: source code, configuration, dependency/build metadata, documentation, and audit evidence.",
        "- Actors: NOT_DETERMINABLE from deterministic repository inspection.",
        "- Trust boundary: repository content is treated as untrusted project data.",
        "- Execution policy: filesystem read-only, network disabled, credentials unavailable unless explicitly granted.",
        "",
        "## APPLICABILITY MATRIX",
        "",
        "| Category | Subcategory | State | Reason |",
        "|---|---|---|---|",
    ]
    for item in prepared.applicability:
        lines.append("| {} | {} | {} | {} |".format(
            item.category, item.subcategory, item.state.value, item.reason
        ))
    lines.extend([
        "",
        "## LIMITATIONS",
        "",
        "- Deterministic discovery and classification do not constitute semantic completeness.",
        "- Production runtime state is NOT_DETERMINABLE unless represented in the target repository.",
        "",
    ])
    return "\n".join(lines)


def render_coverage(
    prepared: PreparedAudit,
    engineering: EngineeringPassResult,
    security: SecurityPassResult,
) -> str:
    all_results = list(engineering.inspections) + list(security.inspections)
    inspected = {item.target_surface: item for item in all_results}
    lines = [
        "# COVERAGE MANIFEST",
        "",
        "## FILE COVERAGE",
        "",
        "| File | Type | State | Categories | Notes |",
        "|---|---|---|---|---|",
    ]
    for item in prepared.file_classifications:
        lines.append("| {} | {} | MAPPED | {} | Discovery/classification only |".format(
            item.path, item.kind.value, ", ".join(item.domains) or "—"
        ))
    lines.extend([
        "",
        "## INSPECTION COVERAGE",
        "",
        "| Category | Subcategory | State | Result | Scope/Evidence |",
        "|---|---|---|---|---|",
    ])
    for item in prepared.work_items:
        result = inspected.get(item.target_surface)
        category, _, subcategory = item.target_surface.partition("/")
        if result is None:
            state, result_state, evidence = "NOT_INSPECTED", "NOT_DETERMINABLE", "Reserved for another pass"
        else:
            state = "INSPECTED"
            result_state = _inspection_result(result.observations)
            evidence = ", ".join(result.source_refs[:6]) or "No direct source path recorded"
        lines.append("| {} | {} | {} | {} | {} |".format(
            category, subcategory, state, result_state, evidence
        ))
    lines.extend([
        "",
        "## EXECUTION LOG",
        "",
        "### Engineering PASS 1",
        "",
        "- Evidence records: {}".format(len(engineering.evidence)),
        "- Mode: deterministic-read-only",
        "",
        "### Security PASS 2",
        "",
        "- Evidence records: {}".format(len(security.evidence)),
        "- Mode: deterministic-read-only",
        "",
        "## LIMITATIONS",
        "",
        "- MAPPED does not mean fully audited.",
        "- NOT_DETERMINABLE means semantic evidence is still required.",
        "",
    ])
    return "\n".join(lines)


def render_report(
    prepared: PreparedAudit,
    engineering: EngineeringPassResult,
    security: SecurityPassResult,
) -> str:
    identity = _identity(prepared)
    engineering_obs = [o for r in engineering.inspections for o in r.observations]
    security_obs = [o for r in security.inspections for o in r.observations]
    lines = [
        "# ANALYTICAL REPORT",
        "",
        "## 1. Resumo Executivo",
        "",
        "The single-agent runtime completed deterministic Engineering PASS 1 and Security PASS 2 over one TargetSnapshot.",
        "Deterministic observations are not automatically classified as confirmed defects or vulnerabilities.",
        "",
        "## 2. Snapshot da Auditoria",
        "",
        "- Repository: {}".format(identity["repository"]),
        "- Commit: {}".format(identity["commit"]),
        "- Snapshot: {}".format(prepared.snapshot.snapshot_fingerprint),
        "",
        "## 3. Propósito",
        "",
        "Record the observable state and evidence required for downstream normalization.",
        "",
        "## 4. Arquitetura",
        "",
        "Deterministic inspection recorded source inventory and path-level architectural signals. Semantic dependency-direction analysis remains limited.",
        "",
        "## 5. Modelo de Domínio",
        "",
        "NOT_DETERMINABLE from the current deterministic detector set.",
        "",
        "## 6. Fluxos",
        "",
        "Discovery -> Classification -> Plan -> Engineering PASS 1 -> Security PASS 2 -> Evidence.",
        "",
        "## 7. Qualidade de Código",
        "",
    ]
    quality = [o for o in engineering_obs if o.category == "CODE_QUALITY"]
    lines.extend("- {}".format(o.summary) for o in quality)
    if not quality:
        lines.append("- NOT_DETERMINABLE")
    lines.extend([
        "",
        "## 8. SOLID",
        "",
        "NOT_DETERMINABLE.",
        "",
        "## 9. Design Patterns",
        "",
        "NOT_DETERMINABLE.",
        "",
        "## 10. Banco e Persistência",
        "",
    ])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "DATABASE")
    lines.extend([
        "",
        "## 11. Contrato Domínio -> Banco",
        "",
        "NOT_DETERMINABLE.",
        "",
        "## 12. Build",
        "",
    ])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "BUILD")
    lines.extend([
        "",
        "## 13. Git",
        "",
        "- Working tree: {}.".format(prepared.snapshot.project_state.working_tree_state.value),
        "",
        "## 14. Testes",
        "",
    ])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "TESTING")
    lines.extend(["", "## 15. CI/CD", ""])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "CI_CD")
    lines.extend(["", "## 16. Configuração", ""])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "CONFIGURATION")
    lines.extend(["", "## 17. Documentação", ""])
    lines.extend("- {}".format(o.summary) for o in engineering_obs if o.category == "DOCUMENTATION")
    lines.extend([
        "",
        "## 18. Operação",
        "",
        "NOT_DETERMINABLE.",
        "",
        "## 19. Trade-offs",
        "",
        "Deterministic-first reduces unnecessary model calls at the cost of explicit NOT_DETERMINABLE results where semantics cannot be proved mechanically.",
        "",
        "## 20. Maturidade",
        "",
        "NOT_ASSIGNED until semantic findings, controls, and publication artifacts are complete.",
        "",
        "## 21. Security Review",
        "",
    ])
    lines.extend("- {}".format(o.summary) for o in security_obs)
    lines.extend([
        "",
        "## 22. Correlação de Riscos",
        "",
        "Both passes reference the same TargetSnapshot. Causal correlation beyond shared scope is not inferred here.",
        "",
        "## 23. Pontos Fortes",
        "",
        "- Immutable snapshot reference.",
        "- Same AuditRun across both passes.",
        "- Read-only deterministic execution.",
        "- Security observations are not promoted automatically to vulnerabilities.",
        "",
        "## 24. Problemas Prioritários",
        "",
        "No formal finding was emitted by the deterministic passes.",
        "",
        "## 25. Plano de Evolução",
        "",
        "Add semantic confirmation, positive controls, final ledger semantics, and downstream audit-normalize integration.",
        "",
        "## 26. O que não fazer agora",
        "",
        "- Do not introduce multi-agent audit runtime.",
        "- Do not introduce distributed infrastructure.",
        "- Do not replace deterministic checks with LLM calls when rules/static analysis suffice.",
        "",
        "## 27. Limitações da Auditoria",
        "",
        "- Semantic engineering analysis is incomplete.",
        "- No external CVE/SAST tool is invoked by these deterministic passes.",
        "- Exact source line numbers are not manufactured.",
        "",
        "## 28. Conclusão",
        "",
        "The runtime now executes both audit perspectives as one single-agent run and persists evidence for downstream processing.",
        "",
    ])
    return "\n".join(lines)


def render_ledger(
    engineering: EngineeringPassResult,
    security: SecurityPassResult,
) -> str:
    lines = [
        "# AUDIT LEDGER",
        "",
        "## Findings",
        "",
        "No formal finding was emitted automatically by deterministic inspection.",
        "",
        "## Controls",
        "",
        "No positive control was formalized automatically in this phase.",
        "",
        "## Inspection Observations",
        "",
    ]
    for result in list(engineering.inspections) + list(security.inspections):
        lines.append("### {}".format(result.target_surface))
        for obs in result.observations:
            lines.append("- {} — {} — {}".format(obs.code, obs.state, obs.summary))
            if obs.source_refs:
                lines.append("  - Sources: {}".format(", ".join(obs.source_refs)))
        lines.append("")
    lines.extend([
        "## LIMITATIONS",
        "",
        "- Observations are evidence of inspected patterns, not proof of exploitability.",
        "- Semantic confirmation is required before creating CONFIRMED findings.",
        "",
    ])
    return "\n".join(lines)


def write_audit_artifacts(
    output_dir: str,
    prepared: PreparedAudit,
    engineering: EngineeringPassResult,
    security: SecurityPassResult,
) -> Dict[str, str]:
    root = Path(output_dir)
    paths = {
        "inventory": str(root / "00_inventory_and_threat_model.md"),
        "coverage": str(root / "01_coverage_manifest.md"),
        "report": str(root / "02_analytical_report.md"),
        "ledger": str(root / "03_audit_ledger.md"),
    }
    _write(Path(paths["inventory"]), render_inventory(prepared))
    _write(Path(paths["coverage"]), render_coverage(prepared, engineering, security))
    _write(Path(paths["report"]), render_report(prepared, engineering, security))
    _write(Path(paths["ledger"]), render_ledger(engineering, security))
    return paths
