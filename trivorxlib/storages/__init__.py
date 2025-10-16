"""TrivorX storage package.

Provides query primitives, sorting utilities, base storage interfaces,
and concrete storage backends. Common symbols are re-exported for
convenient access via ``trivorxlib.storages``.
"""

from .base import (
    TXStorageQueryOps,
    TXQueryNode,
    TXCondition,
    TXUnaryQuery,
    TXLogicalQuery,
    txquery_from_dict,
    TXSortDirection,
    TXSortCriterion,
    txsort_from_dict,
    TXStorageBase,
)

from .mysql import (
    TXSQLBuilder,
    TXMySQLStorage,
)

__all__ = [
    # Query primitives
    "TXStorageQueryOps",
    "TXQueryNode",
    "TXCondition",
    "TXUnaryQuery",
    "TXLogicalQuery",
    "txquery_from_dict",
    # Sorting
    "TXSortDirection",
    "TXSortCriterion",
    "txsort_from_dict",
    # Base interface
    "TXStorageBase",
    # MySQL backend
    "TXSQLBuilder",
    "TXMySQLStorage",
]