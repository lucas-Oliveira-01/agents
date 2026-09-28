import pytest
from project_audit.__main__ import main


def test_no_persist_rejects_unsupported_full_before_touching_target(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['project-audit', '--target', str(tmp_path), '--phase', 'full', '--no-persist'])
    # No semantic backend/network should be reached for an invalid mode.
    monkeypatch.setattr('project_audit.__main__.create_local_omniroute_backend', lambda: (_ for _ in ()).throw(AssertionError('backend must not be called')))
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not list(tmp_path.iterdir())


def test_full_transport_initialization_failure_is_not_complete(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['project-audit', '--target', str(tmp_path), '--phase', 'full'])
    def unavailable():
        raise ConnectionError('gateway unavailable')
    monkeypatch.setattr('project_audit.__main__.create_local_omniroute_backend', unavailable)
    assert main() != 0
    captured = capsys.readouterr()
    assert 'execution=COMPLETE' not in captured.out
    assert 'TRANSPORT_FAILURE' in captured.err
    assert not (tmp_path / '.audit' / '02_analytical.md').exists()
