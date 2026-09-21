"""Tests for parsing varied markdown formats, structures, taxonomies, and references in audit-normalize."""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_varied_markdown_structures():
    """Verify parsing of list-based, table-based, Portuguese headings, and numbered sections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, "relatorio_auditoria.md")
        with open(doc_path, "w") as f:
            f.write("""# RELATÓRIO DE AUDITORIA TÉCNICA

## 1. Identidade do Projeto
- Project Name: smartserv
- Repositório: smartserv
- Target Commit: f7798ca700166e618389c1d1a9037a1ab2c32e7e
- Branch: main
- Version: 1.0.0

## 2. Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SEGURANÇA | AUTENTICAÇÃO | APPLICABLE |
| BANCO DE DADOS | TRANSAÇÕES | APPLICABLE |

## 3. Cobertura de Inspeção
| Categoria | Subcategoria | Estado | Resultado | Escopo |
| SEGURANÇA | AUTENTICAÇÃO | INSPECTED | FINDINGS_PRESENT | auth service |
| BANCO DE DADOS | TRANSAÇÕES | INSPECTED | FINDINGS_PRESENT | db transactions |

## 4. Limitações
- Análise estática realizada sem execução de testes dinâmicos de carga.
- Ambiente de staging não acessível durante a auditoria.

## 5. Vulnerabilidades e Problemas
### SEC-001: Falha no controle de CORS
Category: SECURITY
Subcategory: CORS
Type: RISK
Status: CONFIRMED
Severity: Critical
Confidence: HIGH
Location: backend/src/main/java/config/CorsConfig.java:12
Evidence: `it.anyHost();` ativado globalmente
Description: Servidor aceita requisições de qualquer host de origem.
Cause: Configuração permissiva para desenvolvimento local.
Impact: Possibilidade de requisições cross-origin com credenciais.
Exploitability: Moderada se tokens estiverem em cookies sem SameSite.
Recommendation: Configurar domínios explícitos por ambiente.

### CONTROL-001: Criptografia de senhas com Argon2
Category: SECURITY
Subcategory: PASSWORDS
Status: CONFIRMED
Description: O serviço de usuários utiliza Argon2id para hash seguro de credenciais.

## 6. Referências e Padrões
- Padrão avaliado: OWASP Top 10 2021
- Identificador de fraqueza: CWE-942
- Repositório oficial: https://github.com/example/smartserv
- Vulnerabilidade conhecida: CVE-2023-38408
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # Target Project
        assert data["target_project"]["repository"]["state"] == "PRESENT"
        assert data["target_project"]["repository"]["value"] == "smartserv"
        assert data["target_project"]["commit"]["value"] == "f7798ca700166e618389c1d1a9037a1ab2c32e7e"
        assert data["target_project"]["branch"]["value"] == "main"
        assert data["target_project"]["version"]["value"] == "1.0.0"
        assert data["target_project"]["build_version"]["state"] == "NOT_PROVIDED_BY_SOURCE"

        # Applicability
        assert len(data["applicability"]) == 2

        # Inspections
        assert len(data["inspections"]) == 2

        # Limitations
        assert len(data["limitations"]) == 2
        assert data["limitations"][0]["id"] == "LIMIT-001"
        assert data["limitations"][1]["id"] == "LIMIT-002"

        # Findings & Taxonomy mapping (Critical -> P0)
        assert len(data["findings"]) == 1
        f_sec = data["findings"][0]
        assert f_sec["id"] == "SEC-001"
        assert f_sec["severity"]["value"] == "P0"
        assert f_sec["category"] == "SECURITY"
        assert f_sec["location"]["value"]["file"] == "backend/src/main/java/config/CorsConfig.java"
        assert f_sec["location"]["value"]["line"] == 12

        # Controls
        assert len(data["controls"]) == 1
        assert data["controls"][0]["id"] == "CONTROL-001"
        assert data["controls"][0]["status"] == "CONFIRMED"

        # References
        ref_values = {r["value"] for r in data["references"]}
        assert "CVE-2023-38408" in ref_values
        assert "CWE-942" in ref_values
        assert any("OWASP" in v for v in ref_values)
        assert "https://github.com/example/smartserv" in ref_values

        # Metrics
        assert data["metrics"]["findings_total"] == 1
        assert data["metrics"]["severity"]["P0"] == 1
        assert data["metrics"]["controls_total"] == 1
        assert data["metrics"]["inspections_total"] == 2
