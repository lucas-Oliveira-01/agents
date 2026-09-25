"""Tests for the smoke test diagnostic runner.

Tests cover:
- Smoke test runner with mocked MCP gateway
- Step execution and reporting
- Health check step behaviors
- Initialize step behaviors
- Tool discovery step behaviors
- Expected tools validation step
- Minimal delegation step
- Report formatting
- Error and edge case handling
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from omniroute_delegation.mcp_client import (
    MCPClient,
    ToolSchema,
)
from omniroute_delegation.smoke_test import (
    EXPECTED_TOOLS,
    SmokeTestReport,
    SmokeTestRunner,
    StepResult,
    StepStatus,
    format_report,
    main,
)
from tests.helpers import (
    make_initialize_response,
    make_tool_dict,
    make_tools_list_response,
    make_tool_call_response,
)

# ===========================================================================
# Step Result & Report
# ===========================================================================


class TestStepResult:
    """Test StepResult data class."""

    def test_pass_step(self):
        step = StepResult("test", StepStatus.PASS, "Passed")
        assert step.status == StepStatus.PASS

    def test_fail_step(self):
        step = StepResult("test", StepStatus.FAIL, "Failed")
        assert step.status == StepStatus.FAIL


class TestSmokeTestReport:
    """Test SmokeTestReport management."""

    def test_empty_report(self):
        report = SmokeTestReport(endpoint="http://test", health_endpoint="http://test/h")
        assert report.overall_status == StepStatus.PASS
        assert len(report.steps) == 0

    def test_pass_preserves_pass(self):
        report = SmokeTestReport(endpoint="", health_endpoint="")
        report.add(StepResult("s1", StepStatus.PASS, "OK"))
        assert report.overall_status == StepStatus.PASS

    def test_warn_upgrades_to_warn(self):
        report = SmokeTestReport(endpoint="", health_endpoint="")
        report.add(StepResult("s1", StepStatus.PASS, "OK"))
        report.add(StepResult("s2", StepStatus.WARN, "Warning"))
        assert report.overall_status == StepStatus.WARN

    def test_fail_overrides_warn(self):
        report = SmokeTestReport(endpoint="", health_endpoint="")
        report.add(StepResult("s1", StepStatus.WARN, "Warning"))
        report.add(StepResult("s2", StepStatus.FAIL, "Failed"))
        assert report.overall_status == StepStatus.FAIL

    def test_skip_does_not_change_status(self):
        report = SmokeTestReport(endpoint="", health_endpoint="")
        report.add(StepResult("s1", StepStatus.PASS, "OK"))
        report.add(StepResult("s2", StepStatus.SKIP, "Skipped"))
        assert report.overall_status == StepStatus.PASS


# ===========================================================================
# Report Formatting
# ===========================================================================


class TestReportFormatting:
    """Test terminal report formatting."""

    def test_format_empty_report(self):
        report = SmokeTestReport(
            endpoint="http://test:1234/mcp",
            health_endpoint="http://test:1234/health",
            timestamp="2024-01-01T00:00:00Z",
        )
        output = format_report(report)
        assert "http://test:1234/mcp" in output
        assert "PASS" in output

    def test_format_with_steps(self):
        report = SmokeTestReport(
            endpoint="http://test/mcp",
            health_endpoint="http://test/health",
            timestamp="2024-01-01T00:00:00Z",
        )
        report.add(StepResult("step1", StepStatus.PASS, "OK", 42.0))
        report.add(StepResult("step2", StepStatus.FAIL, "Failed", 0.0))
        output = format_report(report)
        assert "step1" in output
        assert "42ms" in output
        assert "step2" in output
        assert "FAIL" in output

    def test_format_with_details(self):
        report = SmokeTestReport(
            endpoint="http://test/mcp",
            health_endpoint="http://test/health",
        )
        report.add(
            StepResult(
                "step1",
                StepStatus.PASS,
                "OK",
                details={"key": "value"},
            )
        )
        output = format_report(report)
        assert "key: value" in output


# ===========================================================================
# Smoke Test Runner — Full Flow (Mocked)
# ===========================================================================


class TestSmokeTestRunnerFullFlow:
    """Test smoke test runner with fully mocked gateway."""

    def _make_mock_client_success(self) -> MCPClient:
        """Create a mock client that succeeds at all steps."""
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-smoke"},
        )
        tools_response = httpx.Response(
            200,
            json=make_tools_list_response(),
            headers={"mcp-session-id": "sess-smoke"},
        )
        call_response = httpx.Response(
            200,
            json=make_tool_call_response(),
            headers={"mcp-session-id": "sess-smoke"},
        )

        health_response = httpx.Response(200, json={"status": "ok"})

        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.return_value = health_response
        mock_http.post.side_effect = [init_response, tools_response, call_response]

        return MCPClient(http_client=mock_http)

    def test_full_success_run(self):
        client = self._make_mock_client_success()
        runner = SmokeTestRunner(client)
        report = runner.run()

        assert report.overall_status in (StepStatus.PASS, StepStatus.WARN)
        assert len(report.steps) == 6  # All 6 steps executed
        assert report.timestamp  # Timestamp set

        # Health check should pass
        health = next(s for s in report.steps if s.name == "health_check")
        assert health.status == StepStatus.PASS

        # Initialize should pass
        init = next(s for s in report.steps if s.name == "initialize")
        assert init.status == StepStatus.PASS

        # Discover should pass
        discover = next(s for s in report.steps if s.name == "discover_tools")
        assert discover.status == StepStatus.PASS


# ===========================================================================
# Individual Steps
# ===========================================================================


class TestSmokeTestHealthStep:
    """Test health check step in isolation."""

    def test_health_unreachable(self):
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.side_effect = httpx.ConnectError("Refused")

        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_health_check()

        step = runner.report.steps[0]
        assert step.status == StepStatus.FAIL
        assert "unreachable" in step.message.lower() or "refused" in step.message.lower()

    def test_health_http_error(self):
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.return_value = httpx.Response(503, text="Service Unavailable")

        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_health_check()

        step = runner.report.steps[0]
        assert step.status == StepStatus.WARN


class TestSmokeTestInitializeStep:
    """Test initialize step in isolation."""

    def test_initialize_success_with_session(self):
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-ok"},
        )
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.return_value = init_response

        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_initialize()

        step = runner.report.steps[0]
        assert step.status == StepStatus.PASS

    def test_initialize_success_no_session(self):
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={},
        )
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.return_value = init_response

        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_initialize()

        step = runner.report.steps[0]
        assert step.status == StepStatus.WARN

    def test_initialize_failure(self):
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.side_effect = httpx.ConnectError("Refused")

        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_initialize()

        step = runner.report.steps[0]
        assert step.status == StepStatus.FAIL


class TestSmokeTestDiscoverStep:
    """Test tool discovery step."""

    def test_skip_when_not_initialized(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_discover_tools()

        step = runner.report.steps[0]
        assert step.status == StepStatus.SKIP


class TestSmokeTestExpectedToolsStep:
    """Test expected tools validation step."""

    def test_skip_when_no_tools(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        runner = SmokeTestRunner(client)
        runner._step_validate_expected_tools()

        step = runner.report.steps[0]
        assert step.status == StepStatus.SKIP

    def test_all_tools_found(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        # Manually set tools
        for name in EXPECTED_TOOLS:
            client._session.tools[name] = ToolSchema.from_mcp(make_tool_dict(name))

        runner = SmokeTestRunner(client)
        runner._step_validate_expected_tools()

        step = runner.report.steps[0]
        assert step.status == StepStatus.PASS

    def test_missing_tools_warn(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        # Only add some tools
        client._session.tools["delegate_task"] = ToolSchema.from_mcp(
            make_tool_dict("delegate_task")
        )

        runner = SmokeTestRunner(client)
        runner._step_validate_expected_tools()

        step = runner.report.steps[0]
        assert step.status == StepStatus.WARN


class TestSmokeTestMinimalDelegationStep:
    """Test minimal delegation step."""

    def test_skip_when_tool_unavailable(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        client._session.is_initialized = True
        # No tools discovered

        runner = SmokeTestRunner(client)
        runner._step_minimal_delegation()

        step = runner.report.steps[0]
        assert step.status == StepStatus.SKIP

    def test_empty_result_fails(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        client._session.is_initialized = True
        client._session.tools["delegate_task"] = ToolSchema.from_mcp(make_tool_dict())
        client.call_tool = MagicMock(return_value=None)
        runner = SmokeTestRunner(client)
        runner._step_minimal_delegation()
        assert runner.report.steps[0].status == StepStatus.FAIL

    def test_result_without_marker_fails(self):
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        client._session.is_initialized = True
        client._session.tools["delegate_task"] = ToolSchema.from_mcp(make_tool_dict())
        client.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "OK"}]})
        runner = SmokeTestRunner(client)
        runner._step_minimal_delegation()
        assert runner.report.steps[0].status == StepStatus.FAIL

    def test_warn_report_returns_nonzero_exit_code(self, monkeypatch):
        report = SmokeTestReport(endpoint="", health_endpoint="")
        report.add(StepResult("health_check", StepStatus.WARN, "unavailable"))

        class FakeClient:
            mcp_url = "http://test/mcp"
            health_url = "http://test/health"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        monkeypatch.setattr("omniroute_delegation.smoke_test.MCPClient", FakeClient)
        monkeypatch.setattr(
            "omniroute_delegation.smoke_test.SmokeTestRunner.run", lambda self: report
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
