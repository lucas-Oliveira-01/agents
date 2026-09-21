"""Integration tests executing audit-normalize against real audit Markdown fixtures (audit-v1)."""

import json
import os
import tempfile
import pytest

from audit_normalize.normalize import normalize
from audit_normalize.validator import AuditDataValidator, get_default_schema_path


def get_audit_v1_dir():
    env_path = os.environ.get("AUDIT_V1_DIR")
    if env_path and os.path.isdir(env_path):
        return os.path.abspath(env_path)
    workspace_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../audit-v1"))
    if os.path.isdir(workspace_path):
        return workspace_path
    return None


@pytest.fixture
def audit_v1_path():
    p = get_audit_v1_dir()
    if not p:
        pytest.skip("Real fixtures audit-v1 directory not available in environment.")
    return p


def test_real_fixtures_field_level_extraction(audit_v1_path):
    """Test full normalization against real audit-v1 fixtures and verify every field individually."""
    with tempfile.TemporaryDirectory() as out_dir:
        res = normalize(
            input_paths=[audit_v1_path],
            output_dir=out_dir,
            schema_path=get_default_schema_path(),
            base_dir=audit_v1_path,
        )

        assert res["overall_status"] == "VALID"
        assert res["sources_processed"] == 4
        assert res["counts"]["findings"] == 4
        assert res["counts"]["controls"] == 4
        assert res["counts"]["anomalies"] == 0
        assert res["counts"]["conflicts"] == 0

        # Reopen file directly from filesystem per contract
        report_data_file = os.path.join(out_dir, "report_data.json")
        assert os.path.isfile(report_data_file)
        with open(report_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        findings = {f["id"]: f for f in data["findings"]}
        assert len(findings) == 4
        assert set(findings.keys()) == {"ARCH-001", "SEC-001", "TEST-001", "DOC-001"}

        # 1. Individual verification for ARCH-001
        arch = findings["ARCH-001"]
        assert arch["id"] == "ARCH-001"
        assert arch["title"] == "Missing transaction boundaries for multi-statement operations"
        assert arch["category"] == "ARCHITECTURE"
        assert arch["subcategory"] == "TRANSACTION_MANAGEMENT"
        assert arch["type"]["state"] == "PRESENT"
        assert arch["type"]["value"] == "ARCHITECTURAL_DEFECT"
        assert arch["status"]["state"] == "PRESENT"
        assert arch["status"]["value"] == "CONFIRMED"
        assert arch["severity"]["state"] == "PRESENT"
        assert arch["severity"]["value"] == "P2"
        assert arch["confidence"]["state"] == "PRESENT"
        assert arch["confidence"]["value"] == "HIGH"
        assert arch["location"]["state"] == "PRESENT"
        assert arch["location"]["value"]["file"] == "backend/src/main/java/br/com/debuggers/smartserv/service/PedidoService.java"
        assert arch["evidence"]["state"] == "PRESENT"
        assert "itemPedidoDAO.insert" in arch["evidence"]["value"]
        assert "JdbcTransactionManager" in arch["evidence"]["value"]
        assert arch["description"]["state"] == "PRESENT"
        assert "[Observation]: Múltiplas mutações em diferentes tabelas" in arch["description"]["value"]
        # Ensure description is not contaminated by other structured fields
        assert "Recommendation:" not in arch["description"]["value"]
        assert "Injetar o `TransactionManager`" not in arch["description"]["value"]
        assert "Location:" not in arch["description"]["value"]
        assert "backend/src/main" not in arch["description"]["value"]
        assert arch["cause"]["state"] == "PRESENT"
        assert "IoCContainer" in arch["cause"]["value"]
        assert arch["impact"]["state"] == "PRESENT"
        assert "Inconsistência na base de dados" in arch["impact"]["value"]
        assert arch["exploitability"]["state"] == "PRESENT"
        assert "Não aplicável via ator malicioso" in arch["exploitability"]["value"]
        assert arch["recommendation"]["state"] == "PRESENT"
        assert "Injetar o `TransactionManager` nos serviços" in arch["recommendation"]["value"]

        # 2. Individual verification for SEC-001
        sec = findings["SEC-001"]
        assert sec["id"] == "SEC-001"
        assert sec["title"] == "Permissive wildcard CORS configuration"
        assert sec["category"] == "SECURITY"
        assert sec["subcategory"] == "CORS"
        assert sec["type"]["state"] == "PRESENT"
        assert sec["type"]["value"] == "RISK"
        assert sec["status"]["state"] == "PRESENT"
        assert sec["status"]["value"] == "CONFIRMED"
        assert sec["severity"]["state"] == "PRESENT"
        assert sec["severity"]["value"] == "P3"
        assert sec["confidence"]["state"] == "PRESENT"
        assert sec["confidence"]["value"] == "HIGH"
        assert sec["location"]["state"] == "PRESENT"
        assert sec["location"]["value"]["file"] == "backend/src/main/java/br/com/debuggers/smartserv/config/CorsConfig.java"
        assert sec["location"]["value"]["line"] == 12
        assert sec["evidence"]["state"] == "PRESENT"
        assert "it.anyHost();" in sec["evidence"]["value"]
        assert sec["description"]["state"] == "PRESENT"
        assert "[Observation]: O servidor aceita requisições" in sec["description"]["value"]
        assert sec["cause"]["state"] == "PRESENT"
        assert "Conveniência de desenvolvimento" in sec["cause"]["value"]
        assert sec["impact"]["state"] == "PRESENT"
        assert "SameSite" in sec["impact"]["value"]
        assert sec["exploitability"]["state"] == "PRESENT"
        assert "Attack path" in sec["exploitability"]["value"]
        assert sec["recommendation"]["state"] == "PRESENT"
        assert "APP_ENV" in sec["recommendation"]["value"]

        # 3. Individual verification for TEST-001
        tst = findings["TEST-001"]
        assert tst["id"] == "TEST-001"
        assert tst["title"] == "Complete absence of automated tests"
        assert tst["category"] == "TESTING"
        assert tst["subcategory"] == "UNIT_TESTS"
        assert tst["type"]["state"] == "PRESENT"
        assert tst["type"]["value"] == "TECH_DEBT"
        assert tst["status"]["state"] == "PRESENT"
        assert tst["status"]["value"] == "CONFIRMED"
        assert tst["severity"]["state"] == "PRESENT"
        assert tst["severity"]["value"] == "P3"
        assert tst["confidence"]["state"] == "PRESENT"
        assert tst["confidence"]["value"] == "HIGH"
        assert tst["location"]["state"] == "PRESENT"
        assert tst["location"]["value"]["file"] == "backend/src/test"
        assert tst["evidence"]["state"] == "PRESENT"
        assert "pom.xml" in tst["evidence"]["value"]
        assert tst["description"]["state"] == "PRESENT"
        assert "Nenhuma linha de teste" in tst["description"]["value"]
        assert tst["cause"]["state"] == "PRESENT"
        assert "Priorização de requisitos funcionais" in tst["cause"]["value"]
        assert tst["impact"]["state"] == "PRESENT"
        assert "Regressões indetectáveis" in tst["impact"]["value"]
        assert tst["exploitability"]["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert tst["exploitability"]["value"] is None
        assert tst["recommendation"]["state"] == "PRESENT"
        assert "JUnit" in tst["recommendation"]["value"]

        # 4. Individual verification for DOC-001
        doc = findings["DOC-001"]
        assert doc["id"] == "DOC-001"
        assert doc["title"] == "Inconsistency in documented database initialization scripts"
        assert doc["category"] == "DOCUMENTATION"
        assert doc["subcategory"] == "README"
        assert doc["type"]["state"] == "PRESENT"
        assert doc["type"]["value"] == "INCONSISTENCY"
        assert doc["status"]["state"] == "PRESENT"
        assert doc["status"]["value"] == "CONFIRMED"
        assert doc["severity"]["state"] == "PRESENT"
        assert doc["severity"]["value"] == "INFO"
        assert doc["confidence"]["state"] == "PRESENT"
        assert doc["confidence"]["value"] == "HIGH"
        assert doc["location"]["state"] == "PRESENT"
        assert doc["location"]["value"]["file"] == "README.md"
        assert doc["evidence"]["state"] == "PRESENT"
        assert "README cita 6 arquivos SQL" in doc["evidence"]["value"]
        assert doc["description"]["state"] == "PRESENT"
        assert "divergência material" in doc["description"]["value"]
        assert doc["cause"]["state"] == "PRESENT"
        assert "Falta de sincronização" in doc["cause"]["value"]
        assert doc["impact"]["state"] == "PRESENT"
        assert "onboarding" in doc["impact"]["value"]
        assert doc["exploitability"]["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert doc["exploitability"]["value"] is None
        assert doc["recommendation"]["state"] == "PRESENT"
        assert "README.md" in doc["recommendation"]["value"]

        # 5. Verification of Controls
        controls = {c["id"]: c for c in data["controls"]}
        assert len(controls) == 4
        assert set(controls.keys()) == {"CONTROL-001", "CONTROL-002", "CONTROL-003", "CONTROL-004"}
        assert controls["CONTROL-001"]["title"] == "Protection against SQL Injection using PreparedStatement"
        assert controls["CONTROL-001"]["category"] == "SECURITY"
        assert controls["CONTROL-001"]["subcategory"] == "SQL_INJECTION"
        assert controls["CONTROL-001"]["status"] == "CONFIRMED"
        assert "PreparedStatement" in controls["CONTROL-001"]["description"]

        assert controls["CONTROL-002"]["title"] == "Secure Password Hashing"
        assert controls["CONTROL-002"]["category"] == "SECURITY"
        assert controls["CONTROL-002"]["subcategory"] == "PASSWORD_STORAGE"

        assert controls["CONTROL-003"]["title"] == "Authentication Enforcement via Middleware"
        assert controls["CONTROL-003"]["category"] == "SECURITY"
        assert controls["CONTROL-003"]["subcategory"] == "AUTHENTICATION"

        assert controls["CONTROL-004"]["title"] == "Role-based Access Control Configuration"
        assert controls["CONTROL-004"]["category"] == "SECURITY"
        assert controls["CONTROL-004"]["subcategory"] == "AUTHORIZATION"

        # 6. Four-dimension validation gate
        with open(get_default_schema_path(), "r", encoding="utf-8") as sf:
            schema_data = json.load(sf)
        validator = AuditDataValidator(schema_data)
        v_rep = validator.validate_all(data, base_dir=audit_v1_path)
        assert v_rep["overall_status"] == "VALID"
        assert v_rep["validations"]["schema_validation"]["status"] == "PASS"
        assert v_rep["validations"]["semantic_validation"]["status"] == "PASS"
        assert v_rep["validations"]["referential_validation"]["status"] == "PASS"
        assert v_rep["validations"]["integrity_validation"]["status"] == "PASS"
