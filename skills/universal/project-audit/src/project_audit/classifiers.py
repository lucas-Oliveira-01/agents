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
    normalized = task.lower().replace("_", " ")
    if any(token in normalized for token in ("enumerate", "inventory", "extract", "hash", "list files", "manifest")):
        return TaskClassification(task, TaskKind.DETERMINISTIC_EXTRACTION, False, "Task is directly solvable from repository metadata")
    if any(token in normalized for token in ("git diff", "git history", "dependency", "schema inspection", "search for", "preparedstatement")):
        return TaskClassification(task, TaskKind.DETERMINISTIC_ANALYSIS, False, "Task maps to explicit repository/static rules")
    if any(token in normalized for token in ("sql injection", "xss", "ssrf", "secret", "security pattern", "static scan")):
        return TaskClassification(task, TaskKind.STATIC_ANALYSIS, False, "Static analysis should be attempted before semantic escalation")
    return TaskClassification(task, TaskKind.SEMANTIC_ANALYSIS, True, "Task requires interpretation beyond deterministic rules")