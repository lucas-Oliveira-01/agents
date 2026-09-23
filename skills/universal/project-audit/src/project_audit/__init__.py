"""
project_audit — Core Engine V1
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
from .discovery import DiscoverySnapshot, FileRecord, GitMetadata, discover
from .engineering_auditor import EngineeringAuditor, EngineeringInspectionResult, Observation
from .engineering_runner import EngineeringPassResult, execute_engineering_pass
from .models import (
    TargetSnapshot, AuditPlan, AuditWorkItem, Attempt, ExecutionReceipt, Evidence, AuditRun,
    WorkItemAction, ExecutionState, WorkItemFailureState, RunExecutionCompleteness,
    RunCoverageCompleteness, RunFailureState, RunBudgetState, RunPublicationState,
    EvidenceValidity, FindingLifecycle, FindingFingerprint, Provenance, ExecutionPolicy,
    EgressPolicy, FilesystemAccess, NetworkAccess, CredentialAccess, EgressDestination,
    TargetMode, WorkingTreeState,
)

__all__ = [
    "ApplicabilityState", "FileKind", "FileClassification", "TaskKind", "TaskClassification",
    "classify_applicability", "classify_files", "classify_stack", "classify_task",
    "DiscoverySnapshot", "FileRecord", "GitMetadata", "discover",
    "EngineeringAuditor", "EngineeringInspectionResult", "Observation",
    "EngineeringPassResult", "execute_engineering_pass",
    "TargetSnapshot", "AuditPlan", "AuditWorkItem", "Attempt", "ExecutionReceipt", "Evidence", "AuditRun",
    "WorkItemAction", "ExecutionState", "WorkItemFailureState", "RunExecutionCompleteness",
    "RunCoverageCompleteness", "RunFailureState", "RunBudgetState", "RunPublicationState",
    "EvidenceValidity", "FindingLifecycle", "FindingFingerprint", "Provenance", "ExecutionPolicy",
    "EgressPolicy", "FilesystemAccess", "NetworkAccess", "CredentialAccess", "EgressDestination",
    "TargetMode", "WorkingTreeState",
]
