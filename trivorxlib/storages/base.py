from abc import ABC, abstractmethod
from enum import Enum
from trivorxlib.core import *
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

@dataclass
class TXLogicalQuery(TXQueryNode):
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
    """Create a TXQueryNode from a serialized dictionary."""
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
    ASC = "ASC"
    DESC = "DESC"

@dataclass
class TXSortCriterion:
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
    _settings_json: str
    _settings: dict
    def __init__(self, settings_json: str):
        self.settings_json = settings_json
        pass
    @property
    def settings_json(self) -> str:
        return self._settings_json
    @settings_json.setter
    def settings_json(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._settings_json = value
        self._settings = json.loads(value)    
    @abstractmethod
    def get_users(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXUserBase]:
        """
        Retrieve a list of users with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of users matching the criteria.
        """
        pass
    @abstractmethod
    def insert_user(
        self,
        full_name: str,
        login: str,
        role: TXUserRole,
        password: str | None = None,
        encrypted_password: str | None = None,
        uuid: str | None = None,
        token: str | None = None
    ) -> tuple[str, str]:
        """
        Insert a new user into the storage.

        Args:
            full_name: The full name of the user.
            login: The login of the user.
            password: The password of the user.
            role: The role of the user.

        Returns:
            A tuple containing:
            - The UUID of the inserted user.
            - The authentication token associated with the user.
        """
        pass
    
    @abstractmethod
    def update_user(self, uuid: str, token: str | None = None, full_name: str | None = None, login: str | None = None, password: str | None = None, role: TXUserRole | None = None, enabled: bool | None = None, encrypted_password: str | None = None) -> None:
        """
        Update an existing user in the storage.        

        Args:
            uuid: The UUID of the user to update.
            full_name: Optional new full name.
            login: Optional new login.
            password: Optional new password.
            role: Optional new role.
            enabled: Optional new enabled status.
        """
        pass

    @abstractmethod
    def delete_user(self, uuid: str) -> None:
        """
        Delete a user from the storage.

        Args:
            uuid: The UUID of the user to delete.
        """
        pass


