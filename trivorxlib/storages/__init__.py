"""TrivorX storage package.

Provides query primitives, sorting utilities, base storage interfaces,
and concrete storage backends. Common symbols are re-exported for
convenient access via ``trivorxlib.storages``.
"""

# Query primitives and base interfaces
from .base import (
    TXStorageQueryOps,
    TXQueryNode,
    TXCondition,
    TXUnaryQuery,
    TXLogicalQuery,
    TXSortDirection,
    TXSortCriterion,
    TXStorageBase,
)

# Storage backends
from .mysql import (
    TXMySQLStorage,
)

__all__ = [
    # Query primitives
    "TXStorageQueryOps",
    "TXQueryNode",
    "TXCondition",
    "TXUnaryQuery",
    "TXLogicalQuery",
    # Sorting utilities
    "TXSortDirection",
    "TXSortCriterion",
    # Base storage interface
    "TXStorageBase",
    # MySQL backend
    "TXMySQLStorage",
]