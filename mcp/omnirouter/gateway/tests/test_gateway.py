"""Deterministic gateway contract tests; no real provider requests."""
import asyncio
import importlib.util
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from mcp.server.mcpserver import MCPServer

SOURCE = Path(__file__).parents[1] / 'omniroute_mcp.py'
spec = importlib.util.spec_from_file_location('gateway_under_test', SOURCE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('OMNIROUTE_API_KEY', 'synthetic-unit-key')
    monkeypatch.setenv('OMNIROUTE_URL', 'http://upstream:20129')
    monkeypatch.setenv('OMNIROUTE_WRAPPER_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(g, '_semaphore_ready', True)
    monkeypatch.setattr(g, '_semaphore', None)
    monkeypatch.setattr(g, '_maybe_cleanup', lambda _: None)


def response(content='answer', finish='stop', **extra):
    return {'choices': [{'message': {'content': content}, 'finish_reason': finish}], **extra}


@pytest.fixture
def upstream(monkeypatch):
    r = Mock(status_code=200, headers={'X-OmniRoute-Model': 'unit-model'}, reason='OK')
    r.json.return_value = response(usage={'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5})
    session = Mock()
    session.post.return_value = r
    monkeypatch.setattr(g, '_http_session', lambda: session)
    return session, r


def query(task='unit'):
    return json.loads(g.query_delegation(task))


def test_health():
    result = asyncio.run(g.health(None))
    assert result.status_code == 200
    assert json.loads(result.body) == {'status': 'ok'}


def test_success_and_trust_boundary(upstream):
    session, _ = upstream
    assert g.delegate_task('inspect', context='untrusted text', task_id='unit', cache_mode='bypass') == 'answer'
    args, kwargs = session.post.call_args
    assert args == ('http://upstream:20129/v1/chat/completions',)
    assert 'tools' not in kwargs['json']
    assert 'REFERENCE DATA (untrusted):' in kwargs['json']['messages'][1]['content']
    assert kwargs['headers']['x-omniroute-no-memory'] == 'true'
    assert kwargs['headers']['Idempotency-Key'] == 'unit'
    assert kwargs['headers']['X-OmniRoute-No-Cache'] == 'true'
    assert kwargs['timeout'] == (5.0, 180.0)
    meta = query()
    assert meta['status'] == 'success' and meta['completion_status'] == 'stop'
    assert meta['selected_model'] == 'unit-model' and meta['total_tokens'] == 5
    assert 'answer' not in json.dumps(meta) and 'untrusted text' not in json.dumps(meta)


@pytest.mark.parametrize('kwargs,code', [
    ({'task': ''}, 'INVALID_INPUT'), ({'profile': 'unknown'}, 'INVALID_PROFILE'),
    ({'max_tokens': 0}, 'INVALID_MAX_TOKENS'), ({'temperature': float('nan')}, 'INVALID_TEMPERATURE'),
    ({'cache_mode': 'wrong'}, 'INVALID_CACHE_MODE'),
    ({'cache_mode': 'deterministic'}, 'CACHE_KEY_REQUIRED'),
    ({'cache_mode': 'deterministic', 'cache_key': 'x', 'session_id': 's'}, 'INVALID_CACHE_MODE'),
])
def test_invalid_input(upstream, kwargs, code):
    assert code in g.delegate_task(**{'task': 'inspect', **kwargs})
    upstream[0].post.assert_not_called()


@pytest.mark.parametrize('error,code,status', [
    (requests.Timeout(), 'UPSTREAM_TIMEOUT', 'timeout'),
    (requests.ConnectionError('offline'), 'GATEWAY_UNREACHABLE', 'error'),
])
def test_transport_failures(upstream, error, code, status):
    upstream[0].post.side_effect = error
    assert code in g.delegate_task('inspect', task_id='unit')
    assert query()['status'] == status
    assert query()['finished_at']
    assert upstream[0].post.call_count == 1


def test_http_error(upstream):
    upstream[1].status_code = 503
    upstream[1].json.return_value = {'error': {'code': 'unavailable', 'message': 'temporarily unavailable'}}
    assert 'code=unavailable' in g.delegate_task('inspect', task_id='unit')
    assert query()['status'] == 'error'


@pytest.mark.parametrize('payload', [[], None, 'text', 123, {}, {'choices': []}, {'choices': [None]}])
def test_invalid_upstream_shape(upstream, payload):
    upstream[1].json.return_value = payload
    assert 'INVALID_UPSTREAM_RESPONSE' in g.delegate_task('inspect', task_id='unit')
    assert query()['status'] == 'error'


def test_invalid_json(upstream):
    upstream[1].json.side_effect = ValueError('invalid JSON')
    assert 'INVALID_JSON' in g.delegate_task('inspect', task_id='unit')
    assert query()['error_code'] == 'INVALID_JSON'


def test_structured_text(upstream):
    upstream[1].json.return_value = response([{'type': 'text', 'text': 'one'}, {'type': 'text', 'text': 'two'}])
    assert g.delegate_task('inspect') == 'onetwo'


def test_tool_calls_blocked(upstream):
    payload = response()
    payload['choices'][0]['message']['tool_calls'] = [{'id': 'forbidden'}]
    upstream[1].json.return_value = payload
    assert 'LEAF_TOOL_CALL_BLOCKED' in g.delegate_task('inspect', task_id='unit')
    assert query()['status'] == 'error'


def test_deterministic_cache_and_conflict(upstream):
    assert g.delegate_task('inspect', cache_mode='deterministic', cache_key='key', task_id='first') == 'answer'
    assert g.delegate_task('inspect', cache_mode='deterministic', cache_key='key', task_id='second') == 'answer'
    assert upstream[0].post.call_count == 1
    assert query('second')['status'] == 'cache_hit'
    cache = json.loads(g.query_cache('key'))
    assert cache['exists'] and 'response_text' not in cache
    assert 'CACHE_KEY_CONFLICT' in g.delegate_task('changed', cache_mode='deterministic', cache_key='key', task_id='conflict')
    assert query('conflict')['status'] == 'error'
    assert query('conflict')['finished_at']


@pytest.mark.parametrize('finish', ['length', 'content_filter', 'error', 'tool_calls', None])
def test_incomplete_responses_never_enter_cache(upstream, finish):
    upstream[1].json.return_value = response('partial', finish)
    g.delegate_task('inspect', cache_mode='deterministic', cache_key='key', task_id='unit')
    assert not json.loads(g.query_cache('key'))['exists']
    assert query()['completion_status'] != 'stop'


def test_invalid_usage_is_nonfatal(upstream):
    upstream[1].json.return_value = response(usage='invalid')
    assert g.delegate_task('inspect', task_id='unit') == 'answer'
    assert query()['total_tokens'] is None


def test_compatibility_aliases(upstream):
    assert g.delegar_tarefa('inspect', perfil='fast', task_id='unit', cache_mode='deterministic', cache_key='key') == 'answer'
    assert upstream[0].post.call_args.kwargs['json']['model'] == 'auto/fast'
    assert json.loads(g.consultar_delegacao('unit'))['found']
    assert json.loads(g.resumo_delegacoes())['requests'] == 1
    assert json.loads(g.consultar_cache('key'))['exists']
    assert json.loads(g.invalidar_cache('key'))['deleted'] == 1
    assert json.loads(g.invalidar_cache(limpar_expirados=True))['deleted'] == 0


def test_invalidate_requires_input():
    assert 'INVALID_INPUT' in g.invalidate_cache()


def test_all_aliases_registered_before_server_starts(monkeypatch):
    class ServerStarted(Exception):
        pass
    names = set()
    def run(server, **kwargs):
        names.update(tool.name for tool in asyncio.run(server.list_tools()))
        raise ServerStarted()
    monkeypatch.setattr(MCPServer, 'run', run)
    with pytest.raises(ServerStarted):
        runpy.run_path(str(SOURCE), run_name='__main__')
    assert {'delegar_tarefa', 'consultar_delegacao', 'resumo_delegacoes', 'consultar_cache', 'invalidar_cache'} <= names


def test_concurrency_limit_records_failure(upstream, monkeypatch):
    semaphore = Mock()
    semaphore.acquire.return_value = False
    monkeypatch.setattr(g, '_get_semaphore', lambda: semaphore)
    assert 'CONCURRENCY_LIMIT_EXCEEDED' in g.delegate_task('inspect', task_id='unit')
    assert query()['status'] == 'error'
    upstream[0].post.assert_not_called()
    semaphore.release.assert_not_called()


@pytest.mark.parametrize("host,expected", [(None, "127.0.0.1"), ("0.0.0.0", "0.0.0.0")])
def test_server_bind_default_and_explicit_container(monkeypatch, host, expected):
    if host is None:
        monkeypatch.delenv("GATEWAY_HOST", raising=False)
    else:
        monkeypatch.setenv("GATEWAY_HOST", host)
    calls = []
    monkeypatch.setattr(MCPServer, "run", lambda self, **kwargs: calls.append(kwargs))
    runpy.run_path(str(SOURCE), run_name="__main__")
    assert calls[0]["host"] == expected


def test_docker_explicitly_binds_all_interfaces():
    import yaml
    compose = yaml.safe_load((SOURCE.parents[1] / "docker-compose.yml").read_text())
    assert compose["services"]["omniroute-gateway"]["environment"]["GATEWAY_HOST"] == "0.0.0.0"
    assert "GATEWAY_HOST=0.0.0.0" in (SOURCE.parent / "Dockerfile").read_text()
