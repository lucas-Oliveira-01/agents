from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .discovery import DiscoverySnapshot, FileRecord


class FileKind(str, Enum):
    SOURCE = "SOURCE"
    TEST = "TEST"
    CONFIG = "CONFIG"
    BUILD = "BUILD"
    DATABASE = "DATABASE"
    DOCUMENTATION = "DOCUMENTATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CI_CD = "CI_CD"
    GIT = "GIT"
    GENERATED = "GENERATED"
    UNKNOWN = "UNKNOWN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ApplicabilityState(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


class TaskKind(str, Enum):
    DETERMINISTIC_EXTRACTION = "DETERMINISTIC_EXTRACTION"
    DETERMINISTIC_ANALYSIS = "DETERMINISTIC_ANALYSIS"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"


@dataclass(frozen=True)
class FileClassification:
    path: str
    kind: FileKind
    language: Optional[str]
    domains: Tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ApplicabilityDecision:
    category: str
    subcategory: str
    state: ApplicabilityState
    reason: str
    evidence_paths: Tuple[str, ...]


@dataclass(frozen=True)
class TaskClassification:
    task: str
    kind: TaskKind
    llm_allowed: bool
    reason: str


_SOURCE_LANGUAGES = {
    ".py": "PYTHON",
    ".java": "JAVA",
    ".kt": "KOTLIN",
    ".js": "JAVASCRIPT",
    ".jsx": "JAVASCRIPT",
    ".ts": "TYPESCRIPT",
    ".tsx": "TYPESCRIPT",
    ".go": "GO",
    ".rs": "RUST",
    ".rb": "RUBY",
    ".php": "PHP",
    ".cs": "CSHARP",
    ".cpp": "CPP",
    ".c": "C",
    ".h": "C",
    ".swift": "SWIFT",
}

_BUILD_NAMES = {
    "pom.xml": "MAVEN",
    "build.gradle": "GRADLE",
    "build.gradle.kts": "GRADLE_KOTLIN_DSL",
    "settings.gradle": "GRADLE",
    "settings.gradle.kts": "GRADLE_KOTLIN_DSL",
    "package.json": "NPM",
    "pnpm-lock.yaml": "PNPM",
    "yarn.lock": "YARN",
    "pyproject.toml": "PYTHON_BUILD",
    "requirements.txt": "PYTHON_BUILD",
    "cargo.toml": "CARGO",
    "go.mod": "GO_MODULE",
}


def classify_file(record: FileRecord) -> FileClassification:
    path = record.path
    lower = path.lower()
    name = Path(path).name.lower()

    if lower.startswith(".git/") or name == ".gitignore":
        return FileClassification(path, FileKind.GIT, None, ("GIT",), "Git metadata/control file")
    if lower.startswith(".github/workflows/") or lower.startswith(".gitlab/") or name == ".gitlab-ci.yml":
        return FileClassification(path, FileKind.CI_CD, None, ("CI_CD",), "CI workflow location")
    if any(part in {"target", "build", "dist", "out", "coverage"} for part in Path(path).parts):
        return FileClassification(path, FileKind.GENERATED, None, ("BUILD",), "Generated/build output path")
    if name in {"dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"} or "/k8s/" in f"/{lower}/":
        return FileClassification(path, FileKind.INFRASTRUCTURE, None, ("INFRASTRUCTURE", "CONFIGURATION"), "Container/infrastructure artifact")
    if name in _BUILD_NAMES:
        return FileClassification(path, FileKind.BUILD, None, ("BUILD",), f"Recognized build manifest: {name}")
    if name in {"readme.md", "changelog.md", "contributing.md", "license", "license.md"} or lower.startswith("docs/"):
        return FileClassification(path, FileKind.DOCUMENTATION, None, ("DOCUMENTATION",), "Documentation path/name")
    if lower.endswith(".sql") or "/migrations/" in f"/{lower}/" or name in {"schema.sql", "seed.sql", "data.sql"}:
        return FileClassification(path, FileKind.DATABASE, None, ("DATABASE",), "SQL/schema/migration artifact")
    if any(token in name for token in ("config", "settings", ".env")) or Path(path).suffix.lower() in {".ini", ".conf", ".properties", ".toml", ".yaml", ".yml", ".json"}:
        return FileClassification(path, FileKind.CONFIG, None, ("CONFIGURATION",), "Configuration artifact")
    if Path(path).suffix.lower() in _SOURCE_LANGUAGES:
        language = _SOURCE_LANGUAGES[Path(path).suffix.lower()]
        kind = FileKind.TEST if any(token in lower.split("/") for token in ("test", "tests", "spec", "specs")) or name.endswith(("test.java", "_test.py", ".test.ts", ".spec.ts", ".test.js", ".spec.js")) else FileKind.SOURCE
        return FileClassification(path, kind, language, ("CODE_QUALITY", "ARCHITECTURE", "DOMAIN"), "Recognized source/test language")

    return FileClassification(path, FileKind.UNKNOWN, None, (), "No deterministic classification rule matched")


def classify_files(snapshot: DiscoverySnapshot) -> Tuple[FileClassification, ...]:
    return tuple(classify_file(item) for item in snapshot.files)


def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 128_000) -> str:
    try:
        data = (snapshot.root / path).read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def classify_stack(snapshot: DiscoverySnapshot) -> Tuple[str, ...]:
    technologies = set()
    names = {Path(item.path).name.lower() for item in snapshot.files}
    if "pom.xml" in names:
        technologies.add("MAVEN")
        pom = next(item.path for item in snapshot.files if Path(item.path).name.lower() == "pom.xml")
        if "spring-boot" in _read_text(snapshot, pom).lower():
            technologies.add("SPRING_BOOT")
    if "build.gradle" in names or "build.gradle.kts" in names:
        technologies.add("GRADLE")
    if "package.json" in names:
        technologies.add("NODE_JS")
    if "pyproject.toml" in names or "requirements.txt" in names:
        technologies.add("PYTHON")
    if "cargo.toml" in names:
        technologies.add("RUST")
    if "go.mod" in names:
        technologies.add("GO")
    if any(name in names for name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}):
        technologies.add("DOCKER")
    for item in snapshot.files:
        if item.path.lower().endswith(".java") and not item.binary:
            content = _read_text(snapshot, item.path, 64_000).lower()
            if "postgresql" in content:
                technologies.add("POSTGRESQL")
            if "mysql" in content:
                technologies.add("MYSQL")
            if "jdbc" in content:
                technologies.add("JDBC")
            if "hibernate" in content or "jakarta.persistence" in content:
                technologies.add("JPA_HIBERNATE")
    return tuple(sorted(technologies))


def classify_applicability(snapshot: DiscoverySnapshot, stack: Iterable[str]) -> Tuple[ApplicabilityDecision, ...]:
    stack_set = set(stack)
    classifications = classify_files(snapshot)
    paths = {item.path.lower() for item in snapshot.files}
    source_paths = tuple(item.path for item in classifications if item.kind in {FileKind.SOURCE, FileKind.TEST})
    decisions = []

    def add(category: str, subcategory: str, state: ApplicabilityState, reason: str, evidence: Tuple[str, ...] = ()) -> None:
        decisions.append(ApplicabilityDecision(category, subcategory, state, reason, evidence))

    add("ARCHITECTURE", "STRUCTURE", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source files provide an architecture surface" if source_paths else "No source files identified", source_paths[:8])
    add("CODE_QUALITY", "STATIC_REVIEW", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source/test files identified" if source_paths else "No source files identified", source_paths[:8])
    tests = tuple(item.path for item in classifications if item.kind == FileKind.TEST)
    add("TESTING", "TEST_SUITE", ApplicabilityState.APPLICABLE if tests else ApplicabilityState.NOT_DETERMINABLE, "Test files identified" if tests else "No test files identified; absence is not proof of no test mechanism", tests[:8])
    db_evidence = tuple(p for p in paths if p.endswith(".sql"))
    db_present = "JDBC" in stack_set or "JPA_HIBERNATE" in stack_set or bool(db_evidence) or "POSTGRESQL" in stack_set or "MYSQL" in stack_set
    add("DATABASE", "PERSISTENCE", ApplicabilityState.APPLICABLE if db_present else ApplicabilityState.NOT_DETERMINABLE, "Database/persistence indicators found" if db_present else "No decisive persistence evidence", db_evidence[:8])
    ci_evidence = tuple(p for p in paths if p.startswith(".github/workflows/"))
    ci_present = bool(ci_evidence) or ".gitlab-ci.yml" in paths
    add("CI_CD", "PIPELINE", ApplicabilityState.APPLICABLE if ci_present else ApplicabilityState.NOT_DETERMINABLE, "CI configuration discovered" if ci_present else "No CI pipeline identified; absence is not proof of impossibility", ci_evidence[:8])
    infra_evidence = tuple(p for p in paths if Path(p).name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
    add("INFRASTRUCTURE", "CONTAINERS", ApplicabilityState.APPLICABLE if "DOCKER" in stack_set else ApplicabilityState.NOT_DETERMINABLE, "Docker artifacts discovered" if "DOCKER" in stack_set else "No deterministic container indicator", infra_evidence[:8])

    http_evidence = tuple(
        item.path for item in snapshot.files
        if not item.binary and any(
            token in _read_text(snapshot, item.path, 32_000).lower()
            for token in ("httpclient", "resttemplate", "webclient", "requests.get", "axios", "fetch(", "urllib", "httpx")
        )
    )
    add("SECURITY", "SSRF", ApplicabilityState.APPLICABLE if http_evidence else ApplicabilityState.NOT_DETERMINABLE, "Server-side HTTP client indicators found" if http_evidence else "No decisive outbound HTTP evidence", http_evidence[:8])

    frontend_evidence = tuple(item.path for item in snapshot.files if Path(item.path).suffix.lower() in {".html", ".jsx", ".tsx", ".vue", ".svelte"} or item.path.lower().endswith("package.json"))
    add("SECURITY", "XSS", ApplicabilityState.APPLICABLE if frontend_evidence else ApplicabilityState.NOT_DETERMINABLE, "Frontend/template surface identified" if frontend_evidence else "No decisive frontend/template evidence", frontend_evidence[:8])

    secret_surface = tuple(item.path for item in snapshot.files if Path(item.path).name.lower() in {".env", ".env.local", ".env.production", "credentials.json", "secrets.yaml"})
    add("SECURITY", "SECRET_EXPOSURE", ApplicabilityState.APPLICABLE if secret_surface or snapshot.git.is_repository else ApplicabilityState.NOT_DETERMINABLE, "Configuration/history can expose secrets" if secret_surface or snapshot.git.is_repository else "Insufficient project metadata", secret_surface[:8])

    auth_signal = any(token in " ".join(stack_set).lower() for token in ("spring", "jwt", "oauth"))
    add("SECURITY", "AUTHENTICATION", ApplicabilityState.APPLICABLE if auth_signal else ApplicabilityState.NOT_DETERMINABLE, "Authentication-related stack signal found" if auth_signal else "No deterministic authentication mechanism identified")
    add("SECURITY", "AUTHORIZATION", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Authorization semantics require source inspection" if source_paths else "No source evidence")
    sql_present = "JDBC" in stack_set or "JPA_HIBERNATE" in stack_set or bool(db_evidence)
    add("SECURITY", "SQL_INJECTION", ApplicabilityState.APPLICABLE if sql_present else ApplicabilityState.NOT_DETERMINABLE, "SQL/persistence surface identified" if sql_present else "No decisive SQL surface evidence")
    file_surface = any(token in " ".join(paths) for token in ("upload", "download", "multipart", "attachment"))
    add("SECURITY", "FILE_SECURITY", ApplicabilityState.APPLICABLE if file_surface else ApplicabilityState.NOT_DETERMINABLE, "File-transfer surface indicated by paths" if file_surface else "No decisive file-transfer evidence")

    return tuple(decisions)


def classify_task(task: str) -> TaskClassification:
    normalized = task.lower()
    if any(token in normalized for token in ("enumerate", "inventory", "extract", "hash", "list files", "manifest")):
        return TaskClassification(task, TaskKind.DETERMINISTIC_EXTRACTION, False, "Task is directly solvable from repository metadata")
    if any(token in normalized for token in ("git diff", "git history", "dependency", "schema inspection", "search for", "preparedstatement")):
        return TaskClassification(task, TaskKind.DETERMINISTIC_ANALYSIS, False, "Task maps to explicit repository/static rules")
    if any(token in normalized for token in ("sql injection", "xss", "ssrf", "secret", "security pattern", "static scan")):
        return TaskClassification(task, TaskKind.STATIC_ANALYSIS, False, "Static analysis should be attempted before semantic escalation")
    return TaskClassification(task, TaskKind.SEMANTIC_ANALYSIS, True, "Task requires interpretation beyond deterministic rules")
