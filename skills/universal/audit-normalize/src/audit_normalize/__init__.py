"""audit-normalize: Canonical normalizer and validator for Markdown technical audit data."""

__version__ = "1.0.0"

from .models import SourceRole
from .normalize import normalize
from .validator import AuditDataValidator

__all__ = ["SourceRole", "normalize", "AuditDataValidator", "__version__"]
