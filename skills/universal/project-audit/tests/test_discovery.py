import os
import stat

import pytest

from project_audit.discovery import DiscoverySecurityError, discover


def test_discovery_rejects_file_symlink(tmp_path):
    target = tmp_path / "outside.py"
    target.write_text("SECRET = 'outside'\n", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(target)

    with pytest.raises(DiscoverySecurityError):
        discover(str(tmp_path))


def test_discovery_rejects_special_file(tmp_path):
    fifo = tmp_path / "audit.fifo"
    os.mkfifo(fifo)

    with pytest.raises(DiscoverySecurityError):
        discover(str(tmp_path))


def test_discovery_accepts_regular_file(tmp_path):
    source = tmp_path / "main.py"
    source.write_text("print('ok')\n", encoding="utf-8")

    snapshot = discover(str(tmp_path))

    assert snapshot.file("main.py") is not None
    assert snapshot.file("main.py").sha256
