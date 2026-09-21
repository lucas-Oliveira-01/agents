"""Pytest fixtures and configuration for audit-normalize."""

import json
import os
import pytest
from audit_normalize.validator import get_default_schema_path


@pytest.fixture
def canonical_schema():
    schema_path = get_default_schema_path()
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)
