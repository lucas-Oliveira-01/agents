from unittest.mock import MagicMock

import httpx

from omniroute_delegation.mcp_client import MCPClient
from omniroute_delegation.smoke_test import SmokeTestRunner, StepStatus


def test_health_check_warn_on_503():
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = httpx.Response(503, text="Service Unavailable")

    client = MCPClient(http_client=mock_http)
    runner = SmokeTestRunner(client)
    runner._step_health_check()

    step = runner.report.steps[0]
    assert step.status == StepStatus.WARN
    assert "503" in step.message
