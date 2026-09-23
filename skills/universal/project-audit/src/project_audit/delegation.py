
class WorkerPort:
    """
    The port used by the Orchestrator/Auditor to send work across the boundary.
    It bridges the domain (AuditWorkItem) to the infrastructure (DelegationBackend).
    """

    def __init__(self, backend: DelegationBackend, actor_identity: str):
        self.backend = backend
        self.actor_identity = actor_identity

    def execute_delegation(
        self,
        work_item: AuditWorkItem,
        context_payload: Dict[str, Any],
        started_at: datetime,
        data_is_sensitive: Optional[bool] = None,
        target_snapshot_ref: Optional[str] = None,
    ) -> WorkerExecution:
        """
        Translates a WorkItem into a DelegationRequest, executes it via the backend,
        and translates the DelegationResult back into an ExecutionReceipt and Evidence.
        """
        request = DelegationRequest.from_work_item(work_item, context_payload)
        
        # Security Egress Check
        # Unknown sensitivity fails closed before any delegation.
        egress_check = validate_egress_policy(work_item, data_is_sensitive=data_is_sensitive)
        if egress_check.is_error:
            finished_at = datetime.now(timezone.utc)
            receipt = ExecutionReceipt(
                receipt_id=str(uuid.uuid4()),
                work_item_ref=work_item.work_item_id,
                command="omniroute-delegation",
                arguments=[request.request_id],
                policy_snapshot=work_item.effective_execution_policy,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=126,
                artifact_refs=[],
                environment_summary=f"WorkerPort: {self.actor_identity} | error: {egress_check.message}",
            )
            return WorkerExecution(receipt, None, None)

        result = self.backend.delegate(request)
        finished_at = datetime.now(timezone.utc)

        # 1. Translate Status to Exit Code
        if result.status == DelegationStatus.BLOCKED:
            exit_code = 126
        elif result.status == DelegationStatus.SUCCESS:
            exit_code = 0
        else:
            exit_code = 1  # FAILED, TIMEOUT, etc.

        receipt = ExecutionReceipt(
            receipt_id=str(uuid.uuid4()),
            work_item_ref=work_item.work_item_id,
            command="omniroute-delegation",
            arguments=[request.request_id],
            policy_snapshot=work_item.effective_execution_policy,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
            artifact_refs=[],
            environment_summary=f"WorkerPort: {self.actor_identity} | error: {result.error_message}" if result.error_message else None,
        )

        # 2. Build Evidence on success
        evidence = None
        if result.status == DelegationStatus.SUCCESS and result.output_payload and target_snapshot_ref:
            import hashlib
            
            # Deterministic serialization for fingerprint
            raw = json.dumps(result.output_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            fp = hashlib.sha256(raw).hexdigest()

            evidence = Evidence(
                evidence_id=str(uuid.uuid4()),
                target_snapshot_ref=target_snapshot_ref,
                work_item_ref=work_item.work_item_id,
                source_refs=(),
                dependencies=(),
                validity=EvidenceValidity.NOT_DETERMINABLE,
                provenance=Provenance(
                    actor=f"{self.actor_identity} via {result.provider_info or 'unknown'}",
                    generated_at=finished_at,
                ),
                fingerprint=fp,
            )

        return receipt, evidence