"""
project_audit — Swarm-aware audit orchestration
"""

from .classifiers import (
    ApplicabilityState,
    FileKind,
    FileClassification,
    TaskKind,
    TaskClassification,
    classify_applicability,
    classify_files,
    classify_stack,
    classify_task,
)
from .discovery import DiscoverySecurityError, DiscoverySnapshot, FileRecord, GitMetadata, discover
from .engineering_auditor import EngineeringAuditor, EngineeringInspectionResult, Observation
from .engineering_runner import EngineeringPassResult, execute_engineering_pass
from .security_pass import DeterministicSecurityAuditor, SecurityInspectionResult, SecurityObservation
from .security_runner import SecurityPassResult, execute_security_pass
from .semantic_auditor import SemanticAuditor, SemanticFindingCandidate, SemanticReviewResult
from .semantic_runner import execute_semantic_review
from .context_builder import ContextBundle, ContextItem, build_context
from .classification import (
    ClassificationResult,
    ProjectProfile,
    build_classification_results,
    classify_technology_surfaces,
    profile_project,
)
from .sensitivity import SensitivityAssessment, SensitivityState, aggregate_assessments, assess_text
from .report_writer import write_audit_artifacts
from .runtime import FullAuditResult, run_full_audit
from .normalization_runner import NormalizationResult, run_audit_normalize
from .delegation import WorkerExecution
from .autofix import AutoFixError, FixCandidate, FixLedger, logical_finding_key, run_immutable_fix
from .verifier import IndependentVerifier, VerificationResult, VerificationVerdict, candidate_identity, consolidated_reviews, verify_semantic_reviews
from .change_impact import ChangeImpact, ChangeEvent, ChangeKind, EvidenceImpact, build_change_impact
from .incremental import (
    IncrementalDecision,
    DependencyKind,
    DependencyNode,
    EvidenceDependencyGraph,
    IncrementalBinding,
    decide_incremental_action,
    build_dependency_graph,
    plan_incremental_actions,
    match_previous_evidence,
    plan_incremental_actions_stable,
    derive_reused_evidence,
)
from .omniroute_backend import OmniRouteDelegationBackend, create_local_omniroute_backend
from .models import (
    TargetSnapshot, AuditPlan, AuditWorkItem, Attempt, ExecutionReceipt, Evidence, AuditRun,
    WorkItemAction, ExecutionState, WorkItemFailureState, RunExecutionCompleteness,
    RunCoverageCompleteness, RunFailureState, RunBudgetState, RunPublicationState,
    EvidenceValidity, FindingStatus, FindingLifecycle, FindingFingerprint, Provenance, ExecutionPolicy,
    EgressPolicy, FilesystemAccess, NetworkAccess, CredentialAccess, EgressDestination,
    TargetMode, WorkingTreeState, FindingRecord,
)

__all__ = [
    "ApplicabilityState", "FileKind", "FileClassification", "TaskKind", "TaskClassification",
    "classify_applicability", "classify_files", "classify_stack", "classify_task",
    "DiscoverySecurityError", "DiscoverySnapshot", "FileRecord", "GitMetadata", "discover",
    "EngineeringAuditor", "EngineeringInspectionResult", "Observation",
    "EngineeringPassResult", "execute_engineering_pass",
    "SemanticAuditor", "SemanticFindingCandidate", "SemanticReviewResult", "execute_semantic_review",
    "ContextBundle", "ContextItem", "build_context",
    "ClassificationResult", "ProjectProfile", "build_classification_results",
    "classify_technology_surfaces", "profile_project",
    "SensitivityAssessment", "SensitivityState", "aggregate_assessments", "assess_text",
    "WorkerExecution",
    "DeterministicSecurityAuditor", "SecurityInspectionResult", "SecurityObservation", "SecurityPassResult", "execute_security_pass", "write_audit_artifacts", "NormalizationResult", "run_audit_normalize",
    "TargetSnapshot", "AuditPlan", "AuditWorkItem", "Attempt", "ExecutionReceipt", "Evidence", "AuditRun",
    "WorkItemAction", "ExecutionState", "WorkItemFailureState", "RunExecutionCompleteness",
    "RunCoverageCompleteness", "RunFailureState", "RunBudgetState", "RunPublicationState",
    "EvidenceValidity", "FindingStatus", "FindingLifecycle", "FindingFingerprint", "Provenance", "ExecutionPolicy",
    "EgressPolicy", "FilesystemAccess", "NetworkAccess", "CredentialAccess", "EgressDestination", "FindingRecord",
    "TargetMode", "WorkingTreeState",
    "OmniRouteDelegationBackend", "create_local_omniroute_backend",
    "IncrementalDecision", "DependencyKind", "DependencyNode", "EvidenceDependencyGraph",
    "IncrementalBinding", "ReauditNecessity", "assess_reaudit_necessity",
    "ChangeImpact", "ChangeEvent", "ChangeKind", "EvidenceImpact", "build_change_impact",
    "IndependentVerifier", "VerificationResult", "VerificationVerdict", "candidate_identity", "verify_semantic_reviews", "consolidated_reviews",
    "AutoFixError", "FixCandidate", "FixLedger", "logical_finding_key", "run_immutable_fix",
    "decide_incremental_action", "build_dependency_graph", "plan_incremental_actions",
    "match_previous_evidence", "plan_incremental_actions_stable", "derive_reused_evidence",
    "AuditWriterLock", "StateStoreBusyError", "RecoveryBundle",
]

from .state_store import AuditWriterLock, StateStoreBusyError
from .orchestrator import RecoveryBundle
