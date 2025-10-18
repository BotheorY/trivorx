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
        token: str | None = None,
        twofa_seed: str | None = None
    ) -> tuple[str, str]:
        """
        Insert a new user into the storage.

        Args:
            full_name: The full name of the user.
            login: The login of the user.
            password: The password of the user.
            role: The role of the user.
            twofa_seed: Optional 2FA seed string or None for no 2FA.

        Returns:
            A tuple containing:
            - The UUID of the inserted user.
            - The authentication token associated with the user.
        """
        pass
    
    @abstractmethod
    def update_user(self, uuid: str, token: str | None = None, full_name: str | None = None, login: str | None = None, password: str | None = None, role: TXUserRole | None = None, enabled: bool | None = None, encrypted_password: str | None = None, twofa_seed: str | None = None) -> None:
        """
        Update an existing user in the storage.        

        Args:
            uuid: The UUID of the user to update.
            full_name: Optional new full name.
            login: Optional new login.
            password: Optional new password.
            role: Optional new role.
            enabled: Optional new enabled status.
            twofa_seed: Optional 2FA seed string, may be None to clear.
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

    @abstractmethod
    def get_bots(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXBotBase]:
        """
        Retrieve a list of bots with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of bots matching the criteria.
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
        annotations: str | None = None,
        active: bool | None = None,
        uuid: str | None = None,
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
        """
        pass

    @abstractmethod
    def update_bot(
        self,
        uuid: str,
        user_uuid: str | None = None,
        algo_uuid: str | None = None,
        name: str | None = None,
        algo_name: str | None = None,
        algo_ver: str | None = None,
        algo_settings: str | None = None,
        annotations: str | None = None,
        active: bool | None = None,
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
        """
        pass

    @abstractmethod
    def delete_bot(self, uuid: str) -> None:
        """
        Soft-delete a bot from the storage.

        Args:
            uuid: The UUID of the bot to delete.
        """
        pass

    @abstractmethod
    def get_currencies(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXCurrencyBase]:
        """
        Retrieve a list of currencies with optional filtering, pagination, and limit.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of currencies matching the criteria.
        """
        pass

    @abstractmethod
    def insert_currency(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: str | None = None,
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
        """
        pass

    @abstractmethod
    def update_currency(
        self,
        uuid: str,
        long_name: str | None = None,
        short_name: str | None = None,
        currency_type: TXCurrencyType | None = None,
    ) -> None:
        """
        Update an existing currency in the storage.

        Args:
            uuid: The UUID of the currency to update.
            long_name: Optional new full name.
            short_name: Optional new short name/symbol.
            currency_type: Optional new currency type.
        """
        pass

    @abstractmethod
    def delete_currency(self, uuid: str) -> None:
        """
        Soft-delete a currency from the storage.

        Args:
            uuid: The UUID of the currency to delete.
        """
        pass

    @abstractmethod
    def get_exchange_data_sources(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXExchangeDataSourceBase]:
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
        default_for_types: set[TXCurrencyType] | None = None,
        notes: str | None = None,
        uuid: str | None = None,
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
        """
        pass

    @abstractmethod
    def update_exchange_data_source(
        self,
        uuid: str,
        name: str | None = None,
        available_currency_types: set[TXCurrencyType] | None = None,
        connection_data_required: bool | None = None,
        default_for_types: set[TXCurrencyType] | None = None,
        notes: str | None = None,
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
        """
        pass

    @abstractmethod
    def delete_exchange_data_source(self, uuid: str) -> None:
        """
        Soft-delete an exchange data source from the storage.

        Args:
            uuid: The UUID of the exchange data source to delete.
        """
        pass

    # --- EXCHANGE DATA SOURCE CONNECTION DATA ---
    @abstractmethod
    def get_exchange_data_source_connection_data(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXExchangeDataSourceConnectionDataBase]:
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
        uuid: str | None = None,
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
        exchange_data_source_uuid: str | None = None,
        user_uuid: str | None = None,
        connection_data: str | None = None,
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
    def get_currency_exchanges(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXCurrencyExchangeBase]:
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
        exchange_data_source_uuid: str | None = None,
        date_time: int | None = None,
        uuid: str | None = None,
    ) -> str:
        """
        Insert a new currency exchange into the storage.

        Args:
            currency_uuid_source: The UUID of the source currency.
            currency_uuid_target: The UUID of the target currency.
            value: The exchange rate value.
            exchange_data_source_uuid: Optional UUID of the exchange data source.
            uuid: Optional currency exchange UUID (auto-generated if None).

        Returns:
            The UUID of the inserted currency exchange.
        """
        pass

    @abstractmethod
    def update_currency_exchange(
        self,
        uuid: str,
        currency_uuid_source: str | None = None,
        currency_uuid_target: str | None = None,
        value: float | None = None,
        exchange_data_source_uuid: str | None = None,
        date_time: int | None = None
    ) -> None:
        """
        Update an existing currency exchange in the storage.

        Args:
            uuid: The UUID of the currency exchange to update.
            currency_uuid_source: Optional new source currency UUID.
            currency_uuid_target: Optional new target currency UUID.
            value: Optional new exchange rate value.
            exchange_data_source_uuid: Optional new exchange data source UUID.
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
    def get_financial_hubs(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXFinancialHubBase]:
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
        notes: str | None = None,
        uuid: str | None = None,
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
        name: str | None = None,
        allowed_operations: set[TXAssetType] | None = None,
        notes: str | None = None,
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

        Args:
            uuid: The UUID of the financial hub to delete.
        """
        pass

    # --- FINANCIAL HUB CONNECTION DATA ---
    @abstractmethod
    def get_financial_hub_connection_data(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXFinancialHubConnectionDataBase]:
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
        uuid: str | None = None,
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
        financial_hub_uuid: str | None = None,
        user_uuid: str | None = None,
        connection_data: str | None = None,
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
    def get_wallets(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXWalletBase]:
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
        currency_uuid: str | None = None,
        details_data: str | None = None,
        initial_value: float | None = None,
        initial_value_datetime: int | None = None,
        total_value: float | None = None,
        total_value_datetime: int | None = None,
        connection_data: str | None = None,
        uuid: str | None = None,
    ) -> str:
        """
        Insert a new wallet into the storage.

        Args:
            user_uuid: UUID of the wallet owner.
            financial_hub_uuid: UUID of the financial hub for this wallet.
            name: Wallet display name.
            content_type: Type of wallet content (asset or currency variants).
            asset_uuid: Optional asset UUID when content_type is ASSET.
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
        """
        pass

    @abstractmethod
    def update_wallet(
        self,
        uuid: str,
        user_uuid: str | None = None,
        financial_hub_uuid: str | None = None,
        name: str | None = None,
        content_type: TXAssetType | None = None,
        currency_uuid: str | None = None,
        details_data: str | None = None,
        initial_value: float | None = None,
        initial_value_datetime: int | None = None,
        total_value: float | None = None,
        total_value_datetime: int | None = None,
        connection_data: str | None = None,
    ) -> None:
        """
        Update an existing wallet in the storage.

        Args:
            uuid: The UUID of the wallet to update.
            user_uuid: Optional new owner UUID.
            financial_hub_uuid: Optional new financial hub UUID.
            name: Optional new wallet name.
            content_type: Optional new content type.
            asset_uuid: Optional new asset UUID.
            currency_uuid: Optional new currency UUID.
            details_data: Optional new details JSON.
            initial_value: Optional new initial value.
            initial_value_datetime: Optional new initial value timestamp.
            total_value: Optional new total value.
            total_value_datetime: Optional new total value timestamp.
            connection_data: Optional new connection JSON.
        """
        pass

    @abstractmethod
    def delete_wallet(self, uuid: str) -> None:
        """
        Soft-delete a wallet from the storage.

        Args:
            uuid: The UUID of the wallet to delete.
        """
        pass

    # --- TRANSACTIONS ---
    @abstractmethod
    def get_transactions(self, query: TXQueryNode | None = None, sort: list[TXSortCriterion] | None = None, offset: int = 0, limit: int | None = None) -> list[TXTransactionBase]:
        """
        Retrieve a list of transactions with optional filtering, ordering, and pagination.

        Args:
            query: Optional TXQueryNode to filter the results.
            sort: Optional list of TXSortCriterion for ordering.
            offset: Index of the first element to return (default: 0).
            limit: Maximum number of elements to return (default: None, no limit).

        Returns:
            List of TXTransactionBase matching the criteria.
        """
        pass

    @abstractmethod
    def insert_transaction(
        self,
        origin_transaction_uuid: str | None = None,
        source_wallet_uuid: str | None = None,
        target_wallet_uuid: str | None = None,
        bot_uuid: str | None = None,
        start_datetime: int | None = None,
        end_datetime: int | None = None,
        operational_mode: TXTransOperationalMode | None = None,
        source_value: float | None = None,
        target_value: float | None = None,
        status: TXTransStatus | None = None,
        annotations: str | None = None,
        order: int = 0,
        uuid: str | None = None,
    ) -> str:
        """
        Insert a new transaction into the storage.

        Args:
            origin_transaction_uuid: Optional UUID of the origin transaction.
            source_wallet_uuid: Optional UUID of the source wallet.
            target_wallet_uuid: Optional UUID of the target wallet.
            bot_uuid: Optional UUID of the bot.
            start_datetime: Optional start timestamp.
            end_datetime: Optional end timestamp.
            operational_mode: Optional operational mode.
            source_value: Optional source value.
            target_value: Optional target value.
            status: Optional transaction status.
            annotations: Optional annotations.
            order: Transaction order (default: 0).
            uuid: Optional transaction UUID (auto-generated if None).

        Returns:
            The UUID of the inserted transaction.
        """
        pass

    @abstractmethod
    def update_transaction(
        self,
        uuid: str,
        origin_transaction_uuid: str | None = None,
        source_wallet_uuid: str | None = None,
        target_wallet_uuid: str | None = None,
        bot_uuid: str | None = None,
        start_datetime: int | None = None,
        end_datetime: int | None = None,
        operational_mode: TXTransOperationalMode | None = None,
        source_value: float | None = None,
        target_value: float | None = None,
        status: TXTransStatus | None = None,
        annotations: str | None = None,
        order: int | None = None,
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

        Args:
            uuid: The UUID of the transaction to delete.
        """
        pass
