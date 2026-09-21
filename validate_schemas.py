import json
import os
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

schema_dir = "docs/references/schemas"
schemas = {}
registry = Registry()

for fname in os.listdir(schema_dir):
    if not fname.endswith(".json"): continue
    with open(os.path.join(schema_dir, fname)) as f:
        schema = json.load(f)
        schemas[fname] = schema
        resource = Resource.from_contents(schema)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(fname, resource)

def check_fixture(schema_name, instance, expected_valid=True):
    schema = schemas[schema_name]
    validator = Draft202012Validator(schema, registry=registry)
    errors = list(validator.iter_errors(instance))
    
    if expected_valid and errors:
        print(f"❌ {schema_name} should be valid but got:")
        for err in errors: print(f"  - {err.message}")
        return False
    elif not expected_valid and not errors:
        print(f"❌ {schema_name} should be invalid but was valid!")
        return False
    return True

success = True

# 1. AuditPlan
plan_valid = {
  "plan_id": "123e4567-e89b-12d3-a456-426614174000",
  "frozen_at": "2026-09-21T18:00:00Z",
  "target_snapshot_ref": "a"*64,
  "requested_scope": ["FULL"],
  "applicability_decisions": [{
    "domain": "SECURITY", "applicable": True, "decision_basis": "Contains security", "evidence_refs": ["123e4567-e89b-12d3-a456-426614174001"]
  }],
  "resolved_scope": ["SECURITY"],
  "work_items": [{"work_item_id": "123e4567-e89b-12d3-a456-426614174002"}],
  "execution_policy": {"filesystem": "read-only", "network": "disabled", "credentials": "none"},
  "egress_policy": {"destination": "LOCAL_ONLY", "allow_sensitive": False}
}
success &= check_fixture("audit-plan.schema.json", plan_valid, True)

plan_invalid_extra = dict(plan_valid, extra=True)
success &= check_fixture("audit-plan.schema.json", plan_invalid_extra, False)

# 2. AuditWorkItem
wi_valid = {
  "work_item_id": "123e4567-e89b-12d3-a456-426614174000",
  "plan_ref": "123e4567-e89b-12d3-a456-426614174000",
  "auditor": "security-audit",
  "target_surface": "auth",
  "action": "REUSE",
  "decision_basis": "Valid",
  "effective_execution_policy": {"filesystem": "read-only", "network": "disabled", "credentials": "none"},
  "data_egress_policy": {"destination": "LOCAL_ONLY", "allow_sensitive": False},
  "execution_state": "RUNNING",
  "failure_state": "NONE",
  "attempts": [],
  "artifact_refs": []
}
success &= check_fixture("audit-work-item.schema.json", wi_valid, True)

# Enum test
wi_invalid_enum = dict(wi_valid, action="INVALID_ACTION")
success &= check_fixture("audit-work-item.schema.json", wi_invalid_enum, False)

# 3. Evidence
ev_valid = {
  "evidence_id": "123e4567-e89b-12d3-a456-426614174000",
  "target_snapshot_ref": "a"*64,
  "work_item_ref": "123e4567-e89b-12d3-a456-426614174000",
  "source_refs": [],
  "dependencies": [],
  "validity": "VALID",
  "provenance": {"actor": "x", "generated_at": "2026-09-21T18:00:00Z"},
  "fingerprint": "a"*64
}
success &= check_fixture("evidence.schema.json", ev_valid, True)
ev_invalid_missing = dict(ev_valid)
del ev_invalid_missing["validity"]
success &= check_fixture("evidence.schema.json", ev_invalid_missing, False)

# 4. AuditRun
run_valid = {
  "run_id": "123e4567-e89b-12d3-a456-426614174000",
  "target_snapshot_ref": "a"*64,
  "plan_ref": "123e4567-e89b-12d3-a456-426614174000",
  "execution_completeness": "RUNNING",
  "coverage_completeness": "PENDING",
  "failure_state": "NONE",
  "budget_state": "HEALTHY",
  "publication_state": "NOT_PUBLISHED",
  "work_item_refs": [],
  "artifact_refs": []
}
success &= check_fixture("audit-run.schema.json", run_valid, True)

if success: print("All schemas passed structural and ref validation!")
