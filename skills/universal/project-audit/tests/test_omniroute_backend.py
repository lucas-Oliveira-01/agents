import uuid

from project_audit.delegation import DelegationRequest, DelegationStatus
from project_audit.models import CredentialAccess, ExecutionPolicy, FilesystemAccess, NetworkAccess
from project_audit.omniroute_backend import MCPOmniRouteBackend


class FakeBuilder:
    def __init__(self):
        self.values = {}

    def objetivo(self, value):
        self.values["objetivo"] = value
        return self

    def restricoes(self, value):
        self.values["restricoes"] = value
        return self

    def contexto(self, value):
        self.values["contexto"] = value
        return self

    def formato(self, value):
        self.values["formato"] = value
        return self

    def criterios(self, value):
        self.values["criterios"] = value
        return self

    def task_id(self, value):
        self.values["task_id"] = value
        return self

    def temperature(self, value):
        self.values["temperature"] = value
        return self

    def build(self):
        return self.values


def _request() -> DelegationRequest:
    return DelegationRequest(
        request_id="test-req",
        work_item_ref=str(uuid.uuid4()),
        target_surface="CODE_QUALITY/STATIC_REVIEW",
        auditor_name="semantic-auditor",
        context_payload={"source": "print('hello')"},
        execution_policy=ExecutionPolicy(
            filesystem=FilesystemAccess.READ_ONLY,
            network=NetworkAccess.DISABLED,
            credentials=CredentialAccess.NONE,
        ),
    )


def test_omniroute_backend_builds_current_task_contract():
    observed = {}

    def mock_client(server, tool, args):
        observed["server"] = server
        observed["tool"] = tool
        observed["args"] = args
        return {"content": [{"type": "text", "text": '{"findings": []}'}]}

    backend = MCPOmniRouteBackend(mock_client, task_builder_factory=FakeBuilder)
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert observed["server"] == "omnirouter"
    assert observed["tool"] == "delegar_tarefa"
    assert observed["args"]["task_id"] == "test-req"
    assert observed["args"]["temperature"] == 0
    assert "source" in observed["args"]["contexto"]


def test_omniroute_backend_handles_mcp_error():
    def mock_client(server, tool, args):
        return {"isError": True, "error": "Gateway timeout"}

    backend = MCPOmniRouteBackend(mock_client, task_builder_factory=FakeBuilder)
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.FAILED
    assert "error" in result.error_message
    assert result.provider_info == "omniroute/error"


def test_omniroute_backend_handles_exceptions_gracefully():
    def mock_client(server, tool, args):
        raise ConnectionError("Connection refused")

    backend = MCPOmniRouteBackend(mock_client, task_builder_factory=FakeBuilder)
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.FAILED
    assert "Connection refused" in result.error_message
    assert result.provider_info == "omniroute/exception"


def test_omniroute_backend_factory_uses_discovered_schema_filtering() -> None:
    class FakeClient:
        def __init__(self):
            self.called = None
            self.filtered = None

        def filter_optional_params(self, tool, arguments):
            self.filtered = dict(arguments)
            self.filtered.pop("temperature", None)
            return self.filtered

        def call_tool(self, tool, arguments):
            self.called = (tool, arguments)
            return {"content": [{"type": "text", "text": '{"findings": []}'}]}

    from project_audit.omniroute_backend import create_backend_from_mcp_client

    client = FakeClient()
    backend = create_backend_from_mcp_client(client)
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert client.called is not None
    assert client.called[0] == "delegar_tarefa"
    assert "temperature" not in client.called[1]


def test_omniroute_backend_factory_rejects_incompatible_client() -> None:
    from project_audit.omniroute_backend import (
        OmniRouteBackendConfigurationError,
        create_backend_from_mcp_client,
    )

    try:
        create_backend_from_mcp_client(object())
    except OmniRouteBackendConfigurationError:
        return
    raise AssertionError("incompatible client was accepted")
