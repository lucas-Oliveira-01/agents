"""Real, minimal MCP round trip; no target source or credentials in logs."""
import hashlib
import json
import uuid
from omniroute_delegation.mcp_client import MCPClient
from omniroute_delegation.delegation_gateway import DelegationGateway
from omniroute_delegation.contracts import DelegationTask


def unwrap(value):
    if isinstance(value, dict):
        if value.get('structuredContent'):
            return unwrap(value['structuredContent'])
        if 'result' in value:
            return unwrap(value['result'])
        if 'content' in value:
            return unwrap(value['content'])
    if isinstance(value, list):
        return ''.join(x.get('text', '') for x in value if isinstance(x, dict))
    return value


def main():
    task_id = 'acceptance-smoke-' + uuid.uuid4().hex
    with MCPClient(timeout=210) as c:
        print('health=' + str(c.health_check()))
        c.initialize()
        c.discover_tools()
        print('tools=' + json.dumps(sorted(c.session.tools)))
        assert {'delegate_task', 'delegar_tarefa', 'query_delegation', 'invalidar_cache'} <= c.session.tools.keys()
        result = DelegationGateway(c).delegate(DelegationTask(
            task='Return exactly ACCEPTANCE_SMOKE_OK, with no other text.',
            profile='fast', task_id=task_id, cache_mode='bypass', max_tokens=32,
        ))
        print('response=' + json.dumps(result, ensure_ascii=False))
        text = unwrap(result)
        meta = json.loads(unwrap(c.call_tool('query_delegation', {'task_id': task_id})))
        print('telemetry=' + json.dumps(meta, sort_keys=True))
        assert text.strip() == 'ACCEPTANCE_SMOKE_OK', text
        assert meta['status'] == 'success'
        assert meta['completion_status'] == 'stop'
        assert meta['response_hash'] == hashlib.sha256(text.encode()).hexdigest()
        assert meta['cache_source'] == 'omniroute'
        print('MCP_SMOKE=PASS')

if __name__ == '__main__':
    main()
