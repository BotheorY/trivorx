"""TrivorX storage abstractions and query DSL.

Defines query operators (TXStorageQueryOps), node types (TXQueryNode, TXCondition, TXUnaryQuery, TXLogicalQuery), sorting primitives (TXSortDirection, TXSortCriterion), and the abstract storage interface (TXStorageBase) used across TrivorX backends.

Key Features:
- Flexible Query DSL with logical operators (AND, OR, NOT) and comparison operators
- Multi-level sorting with primary and secondary criteria
- Pagination support for large datasets
- UUID-based entity identification and soft-delete functionality
- Comprehensive CRUD operations for all TrivorX domain entities

Usage Patterns:
- Simple filtering: Use TXCondition with comparison operators
- Complex queries: Combine conditions with TXLogicalQuery
- Negation: Apply TXUnaryQuery with NOT operator
- Sorting: Define multiple TXSortCriterion for hierarchical ordering
- Pagination: Use offset and limit parameters for result sets

Architecture:
- Abstract base class TXStorageBase defines the storage contract
- Query nodes (TXCondition, TXUnaryQuery, TXLogicalQuery) form the query DSL
- Sorting primitives (TXSortCriterion, TXSortDirection) handle result ordering
- Serialization helpers enable query persistence and transmission

Serialization helpers:
- txquery_from_dict: reconstruct a TXQueryNode from its dictionary representation.
- txsort_from_dict: reconstruct a TXSortCriterion from its dictionary representation.

Example:
    condition = TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
    query = TXUnaryQuery(TXStorageQueryOps.NOT, condition)
    payload = query.to_dict()
    restored = txquery_from_dict(payload)

Complex query example:
    # Create a complex query: (status = 'active' AND role = 'admin') OR age > 25
    active_admin = TXLogicalQuery(
        TXStorageQueryOps.AND,
        TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active'),
        TXCondition(TXStorageQueryOps.EQUALS, 'role', 'admin')
    )
    age_condition = TXCondition(TXStorageQueryOps.GREATER_THAN, 'age', 25)
    final_query = TXLogicalQuery(TXStorageQueryOps.OR, active_admin, age_condition)

Sorting example:
    sort_criteria = [
        TXSortCriterion('created_at', TXSortDirection.DESC),
        TXSortCriterion('name', TXSortDirection.ASC)
    ]

Thread Safety:
- Storage implementations should be thread-safe for concurrent operations
- Query objects are immutable and can be safely shared across threads
- Results returned by query methods should be independent copies
"""

from trivorxlib.core.base import *
from abc import ABC, abstractmethod
from enum import Enum
import json
from dataclasses import dataclass
from typing import Any, Dict

"""
*************************************************************
[START] STORAGE QUERIES
*************************************************************
Example Usage

- Condition: TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
- Negation: TXUnaryQuery(TXStorageQueryOps.NOT, TXCondition(...))
- Join: TXLogicalQuery(TXStorageQueryOps.AND, left_node, right_node)
- Serialization: node.to_dict()
- Deserialization: txquery_from_dict(dict_payload)
"""
class TXStorageQueryOps(Enum):
    """Operators supported by the storage query DSL.

    Includes logical, comparison, and collection-based operators used by
    TXQueryNode implementations when filtering entities in storage.

    Operator categories:
    - Logical operators: AND, OR, NOT (used in TXLogicalQuery and TXUnaryQuery)
    - Comparison operators: EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN
    - String operators: STARTS_WITH, ENDS_WITH, CONTAINS
    - Collection operators: INCLUDES_VALUES, NOT_INCLUDES_VALUES

    Usage examples:
        # Comparison operators
        TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
        TXCondition(TXStorageQueryOps.GREATER_THAN, 'balance', 1000)
        
        # String operators
        TXCondition(TXStorageQueryOps.STARTS_WITH, 'email', 'admin@')
        TXCondition(TXStorageQueryOps.CONTAINS, 'name', 'john')
        
        # Collection operators
        TXCondition(TXStorageQueryOps.INCLUDES_VALUES, 'tags', ['premium', 'verified'])
    """
    # Logical AND operator: True if both operands are True
    AND = "AND"
    # Logical OR operator: True if at least one operand is True
    OR = "OR"
    # Logical NOT operator: inverts the boolean value
    NOT = "NOT"
    # Equality operator: True if operands are equal
    EQUALS = "EQUALS"
    # Inequality operator: True if operands are not equal
    NOT_EQUALS = "NOT_EQUALS"
    # Greater-than operator: True if left operand > right operand
    GREATER_THAN = "GREATER_THAN"
    # Less-than operator: True if left operand < right operand
    LESS_THAN = "LESS_THAN"
    # Starts-with operator: string begins with a given substring
    STARTS_WITH = "STARTS_WITH"
    # Ends-with operator: string ends with a given substring
    ENDS_WITH = "ENDS_WITH"
    # Contains operator: string contains a given substring
    CONTAINS = "CONTAINS"
    # Includes-values operator: True if the operand contains all specified values
    INCLUDES_VALUES = "INCLUDES_VALUES"
    # Not-includes-values operator: True if the operand does not contain any of the specified values
    NOT_INCLUDES_VALUES = "NOT_INCLUDES_VALUES"

# Query structure to represent search conditions with unary and binary operators
class TXQueryNode(ABC):
    """Abstract base for all query nodes.

    Subclasses must implement `to_dict()` for serialization.
    """
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

# Operator groups for validation
_UNARY_OPS = {TXStorageQueryOps.NOT}
_LOGICAL_OPS = {TXStorageQueryOps.AND, TXStorageQueryOps.OR}
_COMPARISON_OPS = {
    TXStorageQueryOps.EQUALS,
    TXStorageQueryOps.NOT_EQUALS,
    TXStorageQueryOps.GREATER_THAN,
    TXStorageQueryOps.LESS_THAN,
    TXStorageQueryOps.STARTS_WITH,
    TXStorageQueryOps.ENDS_WITH,
    TXStorageQueryOps.CONTAINS,
    TXStorageQueryOps.INCLUDES_VALUES,
    TXStorageQueryOps.NOT_INCLUDES_VALUES,
}

@dataclass
class TXCondition(TXQueryNode):
    """Leaf node representing a comparison on a field.

    This is the most basic query node type, used to filter entities based on field values using various comparison operators.

    Attributes:
        operator: Comparison operator from `TXStorageQueryOps`. Must be a valid comparison operator (not logical operators like AND/OR/NOT).
        field: Field name to compare. Should be a valid field name for the entity type being queried.
        value: Right-hand value used by the operator. Type should match the expected field type (string for text fields, number for numeric fields, etc.).

    Examples:
        # Simple equality check
        TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
        
        # Numeric comparison
        TXCondition(TXStorageQueryOps.GREATER_THAN, 'balance', 1000)
        
        # String pattern matching
        TXCondition(TXStorageQueryOps.STARTS_WITH, 'email', 'admin@')
        
        # Collection operations
        TXCondition(TXStorageQueryOps.INCLUDES_VALUES, 'tags', ['premium', 'verified'])

    Raises:
        ValueError: If `operator` is not a comparison op or `field` is empty.
    """
    operator: TXStorageQueryOps
    field: str
    value: Any
    def __post_init__(self) -> None:
        if self.operator not in _COMPARISON_OPS:
            raise ValueError(f"Invalid operator for condition: {self.operator}")
        if not isinstance(self.field, str) or not self.field:
            raise ValueError("The condition field must be a non-empty string")
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "condition",
            "op": self.operator.value,
            "field": self.field,
            "value": self.value,
        }

@dataclass
class TXUnaryQuery(TXQueryNode):
    """Unary node that applies a NOT operation to a nested node.

    This class represents logical negation of a query condition. It can be used to invert any query node, creating conditions like "not active", "not in US", etc. It can be nested within logical queries for complex conditions.

    Attributes:
        operator: Must be `TXStorageQueryOps.NOT`. This is the only unary operator currently supported by the query DSL.
        operand: The nested `TXQueryNode` to negate. Can be any type of query node (TXCondition, TXLogicalQuery, or TXUnaryQuery for double negation).

    Examples:
        # Simple negation
        TXUnaryQuery(
            TXStorageQueryOps.NOT,
            TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
        )
        # Results in: status != 'active'
        
        # Negation of complex condition
        TXUnaryQuery(
            TXStorageQueryOps.NOT,
            TXLogicalQuery(
                TXStorageQueryOps.AND,
                [
                    TXCondition(TXStorageQueryOps.EQUALS, 'country', 'US'),
                    TXCondition(TXStorageQueryOps.EQUALS, 'status', 'premium')
                ]
            )
        )
        # Results in: NOT (country = 'US' AND status = 'premium')
        
        # Double negation (can be used for clarity in complex queries)
        TXUnaryQuery(
            TXStorageQueryOps.NOT,
            TXUnaryQuery(
                TXStorageQueryOps.NOT,
                TXCondition(TXStorageQueryOps.EQUALS, 'deleted', True)
            )
        )
        # Results in: deleted = True (double negation cancels out)

    Raises:
        ValueError: If `operator` is not NOT or `operand` is not a TXQueryNode.
    """
    operator: TXStorageQueryOps
    operand: TXQueryNode
    def __post_init__(self) -> None:
        if self.operator not in _UNARY_OPS:
            raise ValueError(f"Invalid operator for unary query: {self.operator}")
        if not isinstance(self.operand, TXQueryNode):
            raise ValueError("The operand of the unary query must be a TXQueryNode")
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "unary",
            "op": self.operator.value,
            "operand": self.operand.to_dict(),
        }

@dataclass(frozen=True)
class TXLogicalQuery(TXQueryNode):
    """Represents a logical combination of query nodes.

    This class allows combining two query conditions using logical operators (AND/OR) to create complex filtering criteria. It can be nested to create arbitrarily complex query structures.

    Attributes:
        operator: The logical operator to apply. Must be TXStorageQueryOps.AND or TXStorageQueryOps.OR.
        left: The left TXQueryNode operand. Can be TXCondition, TXLogicalQuery, or TXUnaryQuery.
        right: The right TXQueryNode operand. Can be TXCondition, TXLogicalQuery, or TXUnaryQuery.

    Examples:
        # AND operation
        TXLogicalQuery(
            TXStorageQueryOps.AND,
            TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active'),
            TXCondition(TXStorageQueryOps.GREATER_THAN, 'balance', 1000)
        )
        
        # OR operation
        TXLogicalQuery(
            TXStorageQueryOps.OR,
            TXCondition(TXStorageQueryOps.EQUALS, 'role', 'admin'),
            TXCondition(TXStorageQueryOps.EQUALS, 'role', 'moderator')
        )
        
        # Nested logical operations
        TXLogicalQuery(
            TXStorageQueryOps.AND,
            TXLogicalQuery(
                TXStorageQueryOps.OR,
                TXCondition(TXStorageQueryOps.EQUALS, 'country', 'US'),
                TXCondition(TXStorageQueryOps.EQUALS, 'country', 'CA')
            ),
            TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active')
        )

    Raises:
        ValueError: If operator is not AND or OR, or if left/right operands are not TXQueryNode instances.
    """
    operator: TXStorageQueryOps
    left: TXQueryNode
    right: TXQueryNode
    def __post_init__(self) -> None:
        if self.operator not in _LOGICAL_OPS:
            raise ValueError(f"Invalid operator for binary/logical query: {self.operator}")
        if not isinstance(self.left, TXQueryNode) or not isinstance(self.right, TXQueryNode):
            raise ValueError("The operands of the logical query must be TXQueryNode")
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "logical",
            "op": self.operator.value,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }

def txquery_from_dict(payload: Dict[str, Any]) -> TXQueryNode:
    """Deserialize a query node from a dictionary.

    Args:
        payload: Dictionary produced by `TXQueryNode.to_dict()`.

    Returns:
        A TXQueryNode instance (TXCondition, TXLogicalQuery, or TXUnaryQuery).

    Examples:
        # Simple condition
        condition_dict = {
            "type": "condition",
            "op": "EQUALS",
            "field": "status",
            "value": "active"
        }
        condition = txquery_from_dict(condition_dict)
        
        # Complex logical query
        logical_dict = {
            "type": "logical",
            "op": "AND",
            "left": {
                "type": "condition",
                "op": "EQUALS",
                "field": "status",
                "value": "active"
            },
            "right": {
                "type": "condition",
                "op": "GREATER_THAN",
                "field": "balance",
                "value": 1000
            }
        }
        logical_query = txquery_from_dict(logical_dict)

    Raises:
        ValueError: If the dictionary structure is invalid, unknown, or missing required fields.
        KeyError: If required dictionary keys are missing.
        TypeError: If data is not a dictionary.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")

    t = payload.get("type")
    op_raw = payload.get("op")
    if not t or not op_raw:
        raise ValueError("Payload must include 'type' and 'op'")

    try:
        op = TXStorageQueryOps(op_raw)
    except Exception:
        raise ValueError(f"Unknown operator: {op_raw}")

    if t == "condition":
        return TXCondition(operator=op, field=payload.get("field", ""), value=payload.get("value"))
    elif t == "unary":
        operand = txquery_from_dict(payload.get("operand", {}))
        return TXUnaryQuery(operator=op, operand=operand)
    elif t == "logical":
        left = txquery_from_dict(payload.get("left", {}))
        right = txquery_from_dict(payload.get("right", {}))
        return TXLogicalQuery(operator=op, left=left, right=right)
    else:
        raise ValueError(f"Unknown node type: {t}")
"""
*************************************************************
[END] STORAGE QUERIES
*************************************************************
"""

"""
*************************************************************
[START] STORAGE SORT
*************************************************************
"""
class TXSortDirection(Enum):
    """Sorting direction for `TXSortCriterion`.

    Values:
        ASC: Ascending order.
        DESC: Descending order.
    """
    ASC = "ASC"
    DESC = "DESC"

@dataclass(frozen=True)
class TXSortCriterion:
    """Single sorting criterion for query results.

    Represents a field and direction combination used to sort query results.
    Multiple criteria can be combined to create multi-level sorting.

    Attributes:
        field: Field name to sort by. Should be a valid field name for the entity type being queried. Field names are case-sensitive and should match the exact field names used in the storage schema.
        direction: Sort direction, either TXSortDirection.ASC or TXSortDirection.DESC.

    Examples:
        # Single field sorting
        TXSortCriterion('created_at', TXSortDirection.DESC)
        TXSortCriterion('name', TXSortDirection.ASC)  # ASC is default
        
        # Multi-level sorting (used in lists)
        [
            TXSortCriterion('country', TXSortDirection.ASC),
            TXSortCriterion('balance', TXSortDirection.DESC),
            TXSortCriterion('name', TXSortDirection.ASC)
        ]
        # This would sort by country first, then by balance (descending), then by name

    Note:
        When using multiple sort criteria, the order in the list determines the
        priority of sorting. The first criterion is the primary sort key, the
        second is the secondary key used for ties, and so on.
    """
    field: str
    direction: TXSortDirection = TXSortDirection.ASC
    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field:
            raise ValueError("The sort field must be a non-empty string")
        if not isinstance(self.direction, TXSortDirection):
            raise ValueError("The sort direction must be TXSortDirection")
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "direction": self.direction.value,
        }

def txsort_from_dict(payload: Dict[str, Any]) -> TXSortCriterion:
    """Deserialize a sort criterion from a dictionary.

    Args:
        payload: Dictionary produced by `TXSortCriterion.to_dict()`.

    Returns:
        A TXSortCriterion instance with the specified field and direction.

    Examples:
        # Basic sort criterion
        sort_dict = {
            "field": "created_at",
            "direction": "DESC"
        }
        criterion = txsort_from_dict(sort_dict)
        
        # Multiple criteria (for use in lists)
        sort_criteria = [
            txsort_from_dict({"field": "country", "direction": "ASC"}),
            txsort_from_dict({"field": "balance", "direction": "DESC"})
        ]

    Raises:
        ValueError: If the dictionary structure is invalid, missing required fields or contains invalid direction values.
        TypeError: If data is not a dictionary.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")
    field = payload.get("field", "")
    dir_raw = payload.get("direction", TXSortDirection.ASC.value)
    try:
        direction = TXSortDirection(dir_raw)
    except Exception:
        raise ValueError(f"Unknown sort direction: {dir_raw}")
    return TXSortCriterion(field=field, direction=direction)
"""
*************************************************************
[END] STORAGE SORT
*************************************************************
"""

class TXStorageBase(ABC):
    """Abstract storage interface for TrivorX domain entities.

    Implementations provide CRUD operations for users, bots, currencies,
    exchange data sources, wallets, financial hubs, and transactions.
    Filtering uses the query DSL (`TXQueryNode`), and sorting uses
    `TXSortCriterion`.

    This interface defines the contract that all storage backends must implement, ensuring consistent behavior across different storage systems (MySQL, PostgreSQL, MongoDB, etc.).

    Key features:
    - Query DSL for flexible data filtering and retrieval
    - Sorting capabilities with multiple criteria support
    - Pagination support for large datasets
    - UUID-based entity identification
    - Soft-delete functionality for data integrity

    Instances are initialized with a JSON settings string validated by
    `TXUtils.validate_json`.

    Example:
        # Initialize storage (implementation-specific)
        storage = MySQLStorage('{"host": "localhost", "database": "trivorx"}')
        
        # Query users with filtering and sorting
        active_users = storage.get_users(
            query=TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active'),
            sort=[TXSortCriterion('created_at', TXSortDirection.DESC)],
            limit=10
        )
    """
    _settings_json: str
    _settings: dict
    def __init__(self, settings_json: str):
        self.settings_json = settings_json
        pass
    @property
    def settings_json(self) -> str:
        """Return the storage settings as a JSON string."""
        return self._settings_json
    @settings_json.setter
    def settings_json(self, value: str) -> None:
        """Validate and set storage settings from a JSON string.

        Args:
            value: JSON string containing storage settings.

        Raises:
            ValueError: Propagated if `TXUtils.validate_json` detects invalid JSON.
        """
        TXUtils.validate_json(value)
        self._settings_json = value
        self._settings = json.loads(value)    
    @abstractmethod
    def get_users(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXUserBase]:
        """
        Retrieve a list of users with optional filtering, ordering, pagination, and limit.

        This method provides flexible user retrieval with support for complex queries,
        multi-level sorting, and pagination. It can be used to implement search
        functionality, user listings, and administrative interfaces.

        Args:
            query: Optional TXQueryNode to filter the results. Can be a simple condition (TXCondition) or complex logical combination (TXLogicalQuery). If None, returns all users.
            sort: Optional list of TXSortCriterion for ordering results. Multiple criteria are applied in order (primary, secondary, etc.). If None, results are returned in storage-dependent order.
            offset: Index of the first element to return (default: 0). Used for pagination. Must be non-negative.
            limit: Maximum number of elements to return (default: None, no limit). Used for pagination and performance optimization. Must be positive if specified.

        Returns:
            List of TXUserBase objects matching the criteria, ordered according to sort criteria, paginated according to offset and limit.

        Examples:
            # Get all users
            all_users = storage.get_users()
            
            # Get active users sorted by creation date (newest first)
            active_users = storage.get_users(
                query=TXCondition(TXStorageQueryOps.EQUALS, 'status', 'active'),
                sort=[TXSortCriterion('created_at', TXSortDirection.DESC)]
            )
            
            # Complex query with pagination
            admin_users = storage.get_users(
                query=TXLogicalQuery(
                    TXStorageQueryOps.AND,
                    [
                        TXCondition(TXStorageQueryOps.EQUALS, 'role', 'admin'),
                        TXCondition(TXStorageQueryOps.GREATER_THAN, 'login_count', 10)
                    ]
                ),
                sort=[
                    TXSortCriterion('last_login', TXSortDirection.DESC),
                    TXSortCriterion('full_name', TXSortDirection.ASC)
                ],
                offset=0,
                limit=20
            )

        Raises:
            ValueError: If offset is negative or limit is not positive when specified.
            TypeError: If query is not a TXQueryNode or sort contains non-TXSortCriterion elements.
        """
        pass
    @abstractmethod
    def insert_user(
        self,
        full_name: str,
        login: str,
        role: TXUserRole,
        password: Optional[str] = None,
        encrypted_password: Optional[str] = None,
        uuid: Optional[str] = None,
        token: Optional[str] = None,
        twofa_seed: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Insert a new user into the storage.

        Args:
            full_name: The full name of the user.
            login: The login of the user.
            role: The role of the user.
            password: The password of the user (optional if encrypted_password provided).
            encrypted_password: Pre-encrypted password (optional if password provided).
            uuid: Optional user UUID (auto-generated if None).
            token: Optional authentication token (auto-generated if None).
            twofa_seed: Optional 2FA seed string or None for no 2FA.

        Returns:
            A tuple containing:
            - The UUID of the inserted user.
            - The authentication token associated with the user.

        Raises:
            ValueError: If neither password nor encrypted_password is provided.
            ValueError: If user with same login already exists.
        """
        pass
    
    @abstractmethod
    def update_user(self, uuid: str, token: Optional[str] = None, full_name: Optional[str] = None, login: Optional[str] = None, password: Optional[str] = None, role: Optional[TXUserRole] = None, enabled: Optional[bool] = None, encrypted_password: Optional[str] = None, twofa_seed: Optional[str] = None) -> None:
        """
        Update an existing user in the storage.        

        Args:
            uuid: The UUID of the user to update.
            token: Optional new authentication token.
            full_name: Optional new full name.
            login: Optional new login.
            password: Optional new password (plain text, will be encrypted).
            role: Optional new role.
            enabled: Optional new enabled status.
            encrypted_password: Optional new pre-encrypted password.
            twofa_seed: Optional 2FA seed string, may be None to clear.

        Raises:
            ValueError: If user with specified UUID does not exist.
            ValueError: If new login is already taken by another user.
        """
        pass

    @abstractmethod
    def delete_user(self, uuid: str) -> None:
        """
        Soft-delete a user from the storage.

        This method performs a soft delete, meaning the user record is marked as deleted but not physically removed from storage. This preserves data integrity and allows for potential recovery or audit trails.

        Args:
            uuid: The UUID of the user to delete.

        Raises:
            ValueError: If user with specified UUID does not exist.
        """
        pass

    @abstractmethod
    def get_bots(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXBotBase]:
        """
        Retrieve a list of bots with optional filtering, ordering, and pagination.

        This method provides flexible bot retrieval with support for complex queries,
        multi-level sorting, and pagination. Bots represent automated trading agents
        that execute algorithms on behalf of users.

        Args:
            query: Optional TXQueryNode to filter the results. Can filter by user UUID,
                algorithm UUID, bot name, active status, and other bot fields.
                If None, returns all bots.
            sort: Optional list of TXSortCriterion for ordering results. Common sort
                fields include 'created_at', 'name', 'active'. Multiple criteria
                are applied in order. If None, results are returned in storage-dependent order.
            offset: Index of the first element to return (default: 0). Used for
                pagination. Must be non-negative.
            limit: Maximum number of elements to return (default: None, no limit).
                Used for pagination and performance optimization. Must be positive
                if specified.

        Returns:
            List of TXBotBase objects matching the criteria, ordered according to
            sort criteria, paginated according to offset and limit.

        Examples:
            # Get all active bots for a user
            user_bots = storage.get_bots(
                query=TXLogicalQuery(
                    TXStorageQueryOps.AND,
                    [
                        TXCondition(TXStorageQueryOps.EQUALS, 'user_uuid', user_uuid),
                        TXCondition(TXStorageQueryOps.EQUALS, 'active', True)
                    ]
                ),
                sort=[TXSortCriterion('created_at', TXSortDirection.DESC)]
            )

        Raises:
            ValueError: If offset is negative or limit is not positive when specified.
            TypeError: If query is not a TXQueryNode or sort contains non-TXSortCriterion elements.
        """
        pass

    @abstractmethod
    def insert_bot(
        self,
        user_uuid: str,
        algo_uuid: str,
        name: str,
        algo_name: str,
        algo_ver: str,
        algo_settings: str,
        annotations: Optional[str] = None,
        active: Optional[bool] = None,
        uuid: Optional[str] = None,
    ) -> str:
        """
        Insert a new bot into the storage.

        Args:
            user_uuid: The UUID of the owner user.
            algo_uuid: The UUID of the algorithm used by the bot.
            name: Bot name.
            algo_name: Algorithm name.
            algo_ver: Algorithm version.
            algo_settings: JSON string with algorithm settings.
            annotations: Optional notes.
            active: Optional active state (default False if None).
            uuid: Optional bot UUID (auto-generated if None).

        Returns:
            The UUID of the inserted bot.

        Raises:
            ValueError: If user_uuid does not exist.
            ValueError: If name is empty or invalid.
            ValueError: If algo_settings is not valid JSON.
        """
        pass

    @abstractmethod
    def update_bot(
        self,
        uuid: str,
        user_uuid: Optional[str] = None,
        algo_uuid: Optional[str] = None,
        name: Optional[str] = None,
        algo_name: Optional[str] = None,
        algo_ver: Optional[str] = None,
        algo_settings: Optional[str] = None,
        annotations: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> None:
        """
        Update an existing bot in the storage.

        Args:
            uuid: The UUID of the bot to update.
            user_uuid: Optional new owner user UUID.
            algo_uuid: Optional new algorithm UUID.
            name: Optional new bot name.
            algo_name: Optional new algorithm name.
            algo_ver: Optional new algorithm version.
            algo_settings: Optional JSON string with algorithm settings.
            annotations: Optional notes.
            active: Optional active state.

        Raises:
            ValueError: If bot with specified UUID does not exist.
            ValueError: If new user_uuid does not exist.
            ValueError: If algo_settings is provided but is not valid JSON.
        """
        pass

    @abstractmethod
    def delete_bot(self, uuid: str) -> None:
        """
        Soft-delete a bot from the storage.

        This method performs a soft delete, meaning the bot record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes.

        Args:
            uuid: The UUID of the bot to delete.

        Raises:
            ValueError: If bot with specified UUID does not exist.
        """
        pass

    @abstractmethod
    def get_currencies(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXCurrencyBase]:
        """
        Retrieve a list of currencies with optional filtering, ordering, and pagination.

        This method provides flexible currency retrieval with support for complex queries, multi-level sorting, and pagination. Currencies represent tradable financial instruments like fiat money, cryptocurrencies, or other assets.

        Args:
            query: Optional TXQueryNode to filter the results. Can filter by currency code, name, type (fiat, crypto, commodity), active status, and other currency fields. If None, returns all currencies.
            sort: Optional list of TXSortCriterion for ordering results. Common sort fields include 'code', 'name', 'type', 'active'. Multiple criteria are applied in order. If None, results are returned in storage-dependent order.
            offset: Index of the first element to return (default: 0). Used for pagination. Must be non-negative.
            limit: Maximum number of elements to return (default: None, no limit). Used for pagination and performance optimization. Must be positive if specified.

        Returns:
            List of TXCurrencyBase objects matching the criteria, ordered according to sort criteria, paginated according to offset and limit.

        Examples:
            # Get all active cryptocurrencies
            crypto_currencies = storage.get_currencies(
                query=TXLogicalQuery(
                    TXStorageQueryOps.AND,
                    [
                        TXCondition(TXStorageQueryOps.EQUALS, 'type', 'crypto'),
                        TXCondition(TXStorageQueryOps.EQUALS, 'active', True)
                    ]
                ),
                sort=[TXSortCriterion('market_cap_rank', TXSortDirection.ASC)]
            )

            # Get major fiat currencies
            major_fiat = storage.get_currencies(
                query=TXCondition(TXStorageQueryOps.IN, 'code', ['USD', 'EUR', 'GBP', 'JPY']),
                sort=[TXSortCriterion('code', TXSortDirection.ASC)]
            )

        Raises:
            ValueError: If offset is negative or limit is not positive when specified.
            TypeError: If query is not a TXQueryNode or sort contains non-TXSortCriterion elements.
        """
        pass

    @abstractmethod
    def insert_currency(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: Optional[str] = None,
    ) -> str:
        """
        Insert a new currency into the storage.

        Args:
            long_name: The full name of the currency.
            short_name: The short name/symbol of the currency.
            currency_type: The type of currency (FIAT or CRYPTO).
            uuid: Optional currency UUID (auto-generated if None).

        Returns:
            The UUID of the inserted currency.

        Raises:
            ValueError: If long_name or short_name is empty or invalid.
            ValueError: If currency with same short_name already exists.
            ValueError: If currency_type is not a valid TXCurrencyType.
        """
        pass

    @abstractmethod
    def update_currency(
        self,
        uuid: str,
        long_name: Optional[str] = None,
        short_name: Optional[str] = None,
        currency_type: Optional[TXCurrencyType] = None
    ) -> None:
        """
        Update an existing currency in the storage.

        Args:
            uuid: The UUID of the currency to update.
            long_name: Optional new full name.
            short_name: Optional new short name/symbol.
            currency_type: Optional new currency type.

        Raises:
            ValueError: If currency with specified UUID does not exist.
            ValueError: If new short_name is already taken by another currency.
            ValueError: If currency_type is not a valid TXCurrencyType.
        """
        pass

    @abstractmethod
    def delete_currency(self, uuid: str) -> None:
        """
        Soft-delete a currency from the storage.

        This method performs a soft delete, meaning the currency record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes.

        Args:
            uuid: The UUID of the currency to delete.

        Raises:
            ValueError: If currency with specified UUID does not exist.
        """
        pass

    @abstractmethod
    def get_exchange_data_sources(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXExchangeDataSourceBase]:
        """
        Retrieve a list of exchange data sources with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of exchange data sources matching the criteria.
        """
        pass

    @abstractmethod
    def insert_exchange_data_source(
        self,
        name: str,
        available_currency_types: set[TXCurrencyType],
        connection_data_required: bool,
        default_for_types: Optional[set[TXCurrencyType]] = None,
        notes: Optional[str] = None,
        uuid: Optional[str] = None,
    ) -> str:
        """
        Insert a new exchange data source into the storage.

        Args:
            name: The name of the exchange data source.
            available_currency_types: Set of currency types supported by this source.
            connection_data_required: Whether connection data is required for this source.
            default_for_types: Optional set of currency types for which this is the default source.
            notes: Optional notes about the exchange data source.
            uuid: Optional exchange data source UUID (auto-generated if None).

        Returns:
            The UUID of the inserted exchange data source.

        Raises:
            ValueError: If name is empty or invalid.
            ValueError: If exchange data source with same name already exists.
            ValueError: If available_currency_types or default_for_types contain invalid currency types.
        """
        pass

    @abstractmethod
    def update_exchange_data_source(
        self,
        uuid: str,
        name: Optional[str] = None,
        available_currency_types: Optional[set[TXCurrencyType]] = None,
        connection_data_required: Optional[bool] = None,
        default_for_types: Optional[set[TXCurrencyType]] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Update an existing exchange data source in the storage.

        Args:
            uuid: The UUID of the exchange data source to update.
            name: Optional new name.
            available_currency_types: Optional new set of supported currency types.
            connection_data_required: Optional new connection data requirement flag.
            default_for_types: Optional new set of default currency types.
            notes: Optional new notes.

        Raises:
            ValueError: If exchange data source with specified UUID does not exist.
            ValueError: If new name is already taken by another exchange data source.
            ValueError: If available_currency_types or default_for_types contain invalid currency types.
        """
        pass

    @abstractmethod
    def delete_exchange_data_source(self, uuid: str) -> None:
        """
        Soft-delete an exchange data source from the storage.

        This method performs a soft delete, meaning the exchange data source record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes.

        Args:
            uuid: The UUID of the exchange data source to delete.

        Raises:
            ValueError: If exchange data source with specified UUID does not exist.
        """
        pass

    # --- EXCHANGE DATA SOURCE CONNECTION DATA ---
    @abstractmethod
    def get_exchange_data_source_connection_data(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXExchangeDataSourceConnectionDataBase]:
        """
        Retrieve a list of exchange data source connection data with optional filtering, ordering, and pagination.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of TXExchangeDataSourceConnectionDataBase matching the criteria.
        """
        pass

    @abstractmethod
    def insert_exchange_data_source_connection_data(
        self,
        exchange_data_source_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: Optional[str] = None
    ) -> str:
        """
        Insert a new exchange data source connection data row.

        Args:
            exchange_data_source_uuid: UUID of the exchange data source.
            user_uuid: UUID of the user owning this connection.
            connection_data: JSON string containing connection details.
            uuid: Optional connection data UUID (auto-generated if None).

        Returns:
            The UUID of the inserted connection data.
        """
        pass

    @abstractmethod
    def update_exchange_data_source_connection_data(
        self,
        uuid: str,
        exchange_data_source_uuid: Optional[str] = None,
        user_uuid: Optional[str] = None,
        connection_data: Optional[str] = None
    ) -> None:
        """
        Update an existing exchange data source connection data row.

        Args:
            uuid: The UUID of the connection data to update.
            exchange_data_source_uuid: Optional new data source UUID.
            user_uuid: Optional new user UUID.
            connection_data: Optional new connection JSON string.
        """
        pass

    @abstractmethod
    def delete_exchange_data_source_connection_data(self, uuid: str) -> None:
        """
        Delete an exchange data source connection data row.

        Args:
            uuid: The UUID of the connection data to delete.
        """
        pass

    @abstractmethod
    def get_currency_exchanges(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXCurrencyExchangeBase]:
        """
        Retrieve a list of currency exchanges with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of currency exchanges matching the criteria.
        """
        pass

    @abstractmethod
    def insert_currency_exchange(
        self,
        currency_uuid_source: str,
        currency_uuid_target: str,
        value: float,
        exchange_data_source_uuid: Optional[str] = None,
        date_time: Optional[int] = None,
        uuid: Optional[str] = None,
    ) -> str:
        """
        Insert a new currency exchange into the storage.

        Args:
            currency_uuid_source: The UUID of the source currency.
            currency_uuid_target: The UUID of the target currency.
            value: The exchange rate value.
            exchange_data_source_uuid: Optional UUID of the exchange data source.
            date_time: Optional timestamp (UNIX timestamp in seconds) for when the exchange rate was recorded.
            uuid: Optional currency exchange UUID (auto-generated if None).

        Returns:
            The UUID of the inserted currency exchange.

        Raises:
            ValueError: If currency_uuid_source or currency_uuid_target do not exist.
            ValueError: If exchange_data_source_uuid is provided but does not exist.
            ValueError: If value is not a positive number.
        """
        pass

    @abstractmethod
    def update_currency_exchange(
        self,
        uuid: str,
        currency_uuid_source: Optional[str] = None,
        currency_uuid_target: Optional[str] = None,
        value: Optional[float] = None,
        exchange_data_source_uuid: Optional[str] = None,
        date_time: Optional[int] = None
    ) -> None:
        """
        Update an existing currency exchange in the storage.

        Args:
            uuid: The UUID of the currency exchange to update.
            currency_uuid_source: Optional new source currency UUID.
            currency_uuid_target: Optional new target currency UUID.
            value: Optional new exchange rate value.
            exchange_data_source_uuid: Optional new exchange data source UUID.
            date_time: Optional new timestamp (UNIX timestamp in seconds) for when the exchange rate was recorded.

        Raises:
            ValueError: If currency exchange with specified UUID does not exist.
            ValueError: If referenced currency UUIDs or exchange data source UUID do not exist.
        """
        pass

    @abstractmethod
    def delete_currency_exchange(self, uuid: str) -> None:
        """
        Delete a currency exchange from the storage.

        Args:
            uuid: The UUID of the currency exchange to delete.
        """
        pass

    @abstractmethod
    def get_financial_hubs(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXFinancialHubBase]:
        """
        Retrieve a list of financial hubs with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of financial hubs matching the criteria.
        """
        pass

    @abstractmethod
    def insert_financial_hub(
        self,
        name: str,
        allowed_operations: set[TXAssetType],
        notes: Optional[str] = None,
        uuid: Optional[str] = None
    ) -> str:
        """
        Insert a new financial hub into the storage.

        Args:
            name: The name of the financial hub.
            allowed_operations: Set of allowed asset operations for the hub.
            notes: Optional notes about the financial hub.
            uuid: Optional financial hub UUID (auto-generated if None).

        Returns:
            The UUID of the inserted financial hub.
        """
        pass

    @abstractmethod
    def update_financial_hub(
        self,
        uuid: str,
        name: Optional[str] = None,
        allowed_operations: Optional[set[TXAssetType]] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Update an existing financial hub in the storage.

        Args:
            uuid: The UUID of the financial hub to update.
            name: Optional new name.
            allowed_operations: Optional new set of allowed asset operations.
            notes: Optional new notes.
        """
        pass

    @abstractmethod
    def delete_financial_hub(self, uuid: str) -> None:
        """
        Soft-delete a financial hub from the storage.

        This method performs a soft delete, meaning the financial hub record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes.

        Args:
            uuid: The UUID of the financial hub to delete.

        Raises:
            ValueError: If financial hub with specified UUID does not exist.
        """
        pass

    # --- FINANCIAL HUB CONNECTION DATA ---
    @abstractmethod
    def get_financial_hub_connection_data(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXFinancialHubConnectionDataBase]:
        """
        Retrieve a list of financial hub connection data with optional filtering, ordering, and pagination.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of TXFinancialHubConnectionDataBase matching the criteria.
        """
        pass

    @abstractmethod
    def insert_financial_hub_connection_data(
        self,
        financial_hub_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: Optional[str] = None
    ) -> str:
        """
        Insert a new financial hub connection data row.

        Args:
            financial_hub_uuid: UUID of the financial hub.
            user_uuid: UUID of the user owning this connection.
            connection_data: JSON string containing connection details.
            uuid: Optional connection data UUID (auto-generated if None).

        Returns:
            The UUID of the inserted connection data.
        """
        pass

    @abstractmethod
    def update_financial_hub_connection_data(
        self,
        uuid: str,
        financial_hub_uuid: Optional[str] = None,
        user_uuid: Optional[str] = None,
        connection_data: Optional[str] = None
    ) -> None:
        """
        Update an existing financial hub connection data row.

        Args:
            uuid: The UUID of the connection data to update.
            financial_hub_uuid: Optional new financial hub UUID.
            user_uuid: Optional new user UUID.
            connection_data: Optional new connection JSON string.
        """
        pass

    @abstractmethod
    def delete_financial_hub_connection_data(self, uuid: str) -> None:
        """
        Delete a financial hub connection data row.

        Args:
            uuid: The UUID of the connection data to delete.
        """
        pass

    # --- WALLETS ---
    @abstractmethod
    def get_wallets(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXWalletBase]:
        """
        Retrieve a list of wallets with optional filtering, ordering, and pagination.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of TXWalletBase matching the criteria.
        """
        pass

    @abstractmethod
    def insert_wallet(
        self,
        user_uuid: str,
        financial_hub_uuid: str,
        name: str,
        content_type: TXAssetType,
        currency_uuid: Optional[str] = None,
        details_data: Optional[str] = None,
        initial_value: Optional[float] = None,
        initial_value_datetime: Optional[int] = None,
        total_value: Optional[float] = None,
        total_value_datetime: Optional[int] = None,
        connection_data: Optional[str] = None,
        uuid: Optional[str] = None,
    ) -> str:
        """
        Insert a new wallet into the storage.

        Args:
            user_uuid: UUID of the wallet owner.
            financial_hub_uuid: UUID of the financial hub for this wallet.
            name: Wallet display name.
            content_type: Type of wallet content (asset or currency variants).
            currency_uuid: Optional currency UUID when content_type is CURRENCY_*.
            details_data: Optional JSON with additional details.
            initial_value: Optional initial value.
            initial_value_datetime: Optional UNIX timestamp for initial value.
            total_value: Optional total value.
            total_value_datetime: Optional UNIX timestamp for total value.
            connection_data: Optional JSON with connection details.
            uuid: Optional wallet UUID (auto-generated if None).

        Returns:
            The UUID of the inserted wallet.

        Raises:
            ValueError: If user_uuid or financial_hub_uuid does not exist.
            ValueError: If content_type is invalid for provided currency_uuid.
        """
        pass

    @abstractmethod
    def update_wallet(
        self,
        uuid: str,
        user_uuid: Optional[str] = None,
        financial_hub_uuid: Optional[str] = None,
        name: Optional[str] = None,
        content_type: Optional[TXAssetType] = None,
        currency_uuid: Optional[str] = None,
        details_data: Optional[str] = None,
        initial_value: Optional[float] = None,
        initial_value_datetime: Optional[int] = None,
        total_value: Optional[float] = None,
        total_value_datetime: Optional[int] = None,
        connection_data: Optional[str] = None
    ) -> None:
        """
        Update an existing wallet in the storage.

        Args:
            uuid: The UUID of the wallet to update.
            user_uuid: Optional new owner UUID.
            financial_hub_uuid: Optional new financial hub UUID.
            name: Optional new wallet name.
            content_type: Optional new content type.
            currency_uuid: Optional new currency UUID.
            details_data: Optional new details JSON.
            initial_value: Optional new initial value.
            initial_value_datetime: Optional new initial value timestamp.
            total_value: Optional new total value.
            total_value_datetime: Optional new total value timestamp.
            connection_data: Optional new connection JSON.

        Raises:
            ValueError: If wallet with specified UUID does not exist.
            ValueError: If new user_uuid or financial_hub_uuid does not exist.
        """
        pass

    @abstractmethod
    def delete_wallet(self, uuid: str) -> None:
        """
        Soft-delete a wallet from the storage.

        This method performs a soft delete, meaning the wallet record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes. All associated transactions remain intact.

        Args:
            uuid: The UUID of the wallet to delete.

        Raises:
            ValueError: If wallet with specified UUID does not exist.
        """
        pass

    # --- TRANSACTIONS ---
    @abstractmethod
    def get_transactions(self, query: Optional[TXQueryNode] = None, sort: Optional[list[TXSortCriterion]] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> list[TXTransactionBase]:
        """
        Retrieve a list of transactions with optional filtering, ordering, and pagination.

        This method provides comprehensive transaction retrieval with support for complex queries, multi-level sorting, and pagination. Transactions represent financial operations including trades, transfers, deposits, and withdrawals across different wallets and financial hubs.

        Args:
            query: Optional TXQueryNode to filter the results. Can filter by wallet UUID, transaction type, status, amount, dates, and other transaction fields. If None, returns all transactions.
            sort: Optional list of TXSortCriterion for ordering results. Multiple criteria are applied in order. If None, results are returned in storage-dependent order.
            offset: Index of the first element to return (default: 0). Used for pagination. Must be non-negative.
            limit: Maximum number of elements to return (default: None, no limit). Used for pagination and performance optimization. Must be positive if specified.

        Returns:
            List of TXTransactionBase objects matching the criteria, ordered according to sort criteria, paginated according to offset and limit.

        Examples:
            # Get all transactions for a specific wallet
            wallet_transactions = storage.get_transactions(
                query=TXCondition(TXStorageQueryOps.EQUALS, 'wallet_uuid', wallet_uuid),
                sort=[TXSortCriterion('created_at', TXSortDirection.DESC)]
            )
            
            # Get recent successful transactions above a threshold
            large_transactions = storage.get_transactions(
                query=TXLogicalQuery(
                    TXStorageQueryOps.AND,
                    [
                        TXCondition(TXStorageQueryOps.EQUALS, 'status', 'completed'),
                        TXCondition(TXStorageQueryOps.GREATER_THAN, 'amount', 1000),
                        TXCondition(TXStorageQueryOps.GREATER_THAN, 'created_at', 
                                   int((datetime.now() - timedelta(days=7)).timestamp()))
                    ]
                ),
                sort=[TXSortCriterion('amount', TXSortDirection.DESC)],
                limit=50
            )
            
            # Get transactions by type with pagination
            deposits = storage.get_transactions(
                query=TXCondition(TXStorageQueryOps.EQUALS, 'transaction_type', 'deposit'),
                sort=[
                    TXSortCriterion('created_at', TXSortDirection.DESC),
                    TXSortCriterion('amount', TXSortDirection.DESC)
                ],
                offset=page * page_size,
                limit=page_size
            )

        Raises:
            ValueError: If offset is negative or limit is not positive when specified.
            TypeError: If query is not a TXQueryNode or sort contains non-TXSortCriterion elements.
        """
        pass

    @abstractmethod
    def insert_transaction(
        self,
        origin_transaction_uuid: Optional[str] = None,
        source_wallet_uuid: Optional[str] = None,
        target_wallet_uuid: Optional[str] = None,
        bot_uuid: Optional[str] = None,
        start_datetime: Optional[int] = None,
        end_datetime: Optional[int] = None,
        operational_mode: Optional[TXTransOperationalMode] = None,
        source_value: Optional[float] = None,
        target_value: Optional[float] = None,
        status: Optional[TXTransStatus] = None,
        annotations: Optional[str] = None,
        order: Optional[int] = 0,
        uuid: Optional[str] = None
    ) -> str:
        """
        Insert a new transaction into the storage.

        Transactions represent financial operations including trades, transfers, deposits, and withdrawals. This method creates a new transaction record with the provided parameters.

        Args:
            origin_transaction_uuid: Optional UUID of the origin transaction (for linked transactions like trade pairs).
            source_wallet_uuid: Optional UUID of the source wallet (for transfers and withdrawals).
            target_wallet_uuid: Optional UUID of the target wallet (for transfers and deposits).
            bot_uuid: Optional UUID of the bot that initiated this transaction.
            start_datetime: Optional start timestamp (UNIX timestamp in seconds).
            end_datetime: Optional end timestamp (UNIX timestamp in seconds).
            operational_mode: Optional operational mode indicating transaction type and execution context.
            source_value: Optional source value (amount being transferred/spent).
            target_value: Optional target value (amount being received).
            status: Optional transaction status (pending, completed, failed, etc.).
            annotations: Optional JSON string with additional transaction metadata.
            order: Transaction order for sequencing (default: 0).
            uuid: Optional transaction UUID (auto-generated if None).

        Returns:
            The UUID of the inserted transaction.

        Raises:
            ValueError: If validation fails for provided parameters.
            ValueError: If referenced wallets or bot do not exist.
        """
        pass

    @abstractmethod
    def update_transaction(
        self,
        uuid: str,
        origin_transaction_uuid: Optional[str] = None,
        source_wallet_uuid: Optional[str] = None,
        target_wallet_uuid: Optional[str] = None,
        bot_uuid: Optional[str] = None,
        start_datetime: Optional[int] = None,
        end_datetime: Optional[int] = None,
        operational_mode: Optional[TXTransOperationalMode] = None,
        source_value: Optional[float] = None,
        target_value: Optional[float] = None,
        status: Optional[TXTransStatus] = None,
        annotations: Optional[str] = None,
        order: Optional[int] = None
    ) -> None:
        """
        Update an existing transaction in the storage.

        Args:
            uuid: The UUID of the transaction to update.
            origin_transaction_uuid: Optional new origin transaction UUID.
            source_wallet_uuid: Optional new source wallet UUID.
            target_wallet_uuid: Optional new target wallet UUID.
            bot_uuid: Optional new bot UUID.
            start_datetime: Optional new start timestamp.
            end_datetime: Optional new end timestamp.
            operational_mode: Optional new operational mode.
            source_value: Optional new source value.
            target_value: Optional new target value.
            status: Optional new transaction status.
            annotations: Optional new annotations.
            order: Optional new transaction order.
        """
        pass

    @abstractmethod
    def delete_transaction(self, uuid: str) -> None:
        """
        Soft-delete a transaction from the storage.

        This method performs a soft delete, meaning the transaction record is marked as deleted but not physically removed from storage. This preserves data integrity and maintains historical records for audit purposes. Related transaction data (such as linked transactions via origin_transaction_uuid) remain intact.

        Args:
            uuid: The UUID of the transaction to delete.

        Raises:
            ValueError: If transaction with specified UUID does not exist.
        """
        pass
