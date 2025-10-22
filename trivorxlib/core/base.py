from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Set
import uuid as u
import bcrypt
import json
from typing import TypeVar, Generic, NamedTuple, Optional
from dataclasses import dataclass

T = TypeVar("T")

class TXDataSchemaItem(NamedTuple, Generic[T]):
    """A generic NamedTuple used to describe a single field in a data schema.
    
    This class provides a structured way to define schema items with both
    human-readable names and type information for validation purposes.
    
    Attributes:
        name (str): Human-readable name for the field.
        type (type[T]): Expected Python type for the field value.
        
    Example:
        >>> schema_item = TXDataSchemaItem(name="User ID", type=int)
        >>> print(schema_item.name)  # "User ID"
        >>> print(schema_item.type)  # <class 'int'>
        
        Example dictionary with multiple TXDataSchemaItem elements:
        >>> example_schema: dict[str, TXDataSchemaItem] = {
        ...     "id": TXDataSchemaItem(name="Row ID", type=int),
        ...     "username": TXDataSchemaItem(name="Your Username", type=str),
        ...     "balance": TXDataSchemaItem(name="Your Balance", type=float)
        ... }
    """
    name: str
    type: type[T]
"""
Example dictionary with three TXDataSchemaItem elements
example_schema: dict[str, TXDataSchemaItem] = {
        "id": TXDataSchemaItem(name="Row ID", type=int),
        "username": TXDataSchemaItem(name="Your Username", type=str),
        "balance": TXDataSchemaItem(name="Your Balance", type=float)
}
"""

class TXAlgo(ABC):
    """Abstract interface for trading algorithms.

    Subclasses define algorithm metadata and implement `run()` to execute
    trading logic using a `TXFinancialHubBase` and an exchange data source.
    """

    @staticmethod
    @abstractmethod
    def get_settings_schema() -> dict[str, TXDataSchemaItem]:
        """Return the expected JSON settings schema for this algorithm.

        Returns:
            dict[str, TXDataSchemaItem]: Mapping of setting keys to descriptors
            used to validate the optional `settings` JSON.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable algorithm name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string for the algorithm."""
        pass

    @property
    @abstractmethod
    def uuid(self) -> str:
        """Stable unique identifier for this algorithm."""
        pass

    @abstractmethod
    def run(self, bot: TXBotBase, financial_hub: TXFinancialHubConnectionDataBase, exchange_data_source: TXExchangeDataSourceBase, settings: Optional[str] = None) -> tuple[bool, str | None]:
        """Execute the algorithm once.

        Args:
            bot (TXBotBase): Orchestrating bot instance.
            financial_hub (TXFinancialHubConnectionDataBase): Authenticated financial hub connection data.
            exchange_data_source (TXExchangeDataSourceBase): Market data/exchange provider.
            settings (str | None): Optional JSON settings validated against `get_settings_schema()`.

        Returns:
            tuple[bool, str | None]: `(success, message)` where `message` can be `None`.

        Raises:
            ValueError: If `settings` is invalid per `get_settings_schema()`.
        """
        pass

class TXUtils():
    """Utility class providing static methods for common operations.
    
    This class contains various utility functions for data manipulation,
    validation, file operations, and cryptographic operations used
    throughout the TrivorX library.
    """

    @staticmethod
    def merge_dict(existing: dict, new: dict) -> dict:
        """Recursively merge dictionary data, preserving existing values and updating/adding new ones.
        
        Args:
            existing (dict): The existing dictionary data.
            new (dict): The new dictionary data to merge.
            
        Returns:
            dict: The merged dictionary with nested dictionaries recursively merged.
            
        Example:
            >>> existing = {"a": 1, "b": {"c": 2}}
            >>> new = {"b": {"d": 3}, "e": 4}
            >>> result = TXUtils.merge_dict(existing, new)
            >>> print(result)  # {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
        """
        merged = existing.copy()
        
        for key, value in new.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                merged[key] = TXUtils.merge_dict(merged[key], value)
            else:
                # Update or add the value
                merged[key] = value
        
        return merged

    @staticmethod
    def normalize_coin_name(coin_name: str) -> str:
        """Normalize a coin name to a consistent format.

        Converts the coin name to lowercase and removes spaces to create
        a standardized format for comparison and storage.

        Args:
            coin_name (str): The name of the coin to normalize.

        Returns:
            str: The normalized coin name in lowercase with spaces removed.
            
        Example:
            >>> TXUtils.normalize_coin_name("Bitcoin Cash")
            'bitcoincash'
            >>> TXUtils.normalize_coin_name("ETHEREUM")
            'ethereum'
        """
        return coin_name.lower().replace(" ", "")

    @staticmethod
    def validate_json_schema(json_str: str, schema: dict[str, TXDataSchemaItem]) -> bool:
        """Validate a JSON string against a schema defined by TXDataSchemaItem descriptors.

        Parses the JSON string and validates that all required fields are present
        and match the expected types as defined in the schema.

        Args:
            json_str (str): The JSON string to validate.
            schema (dict[str, TXDataSchemaItem]): A dictionary where keys are expected 
                field names and values are TXDataSchemaItem describing the expected type.

        Returns:
            bool: True if the JSON is valid and conforms to the schema, False otherwise.
            
        Example:
            >>> schema = {
            ...     "id": TXDataSchemaItem(name="ID", type=int),
            ...     "name": TXDataSchemaItem(name="Name", type=str)
            ... }
            >>> TXUtils.validate_json_schema('{"id": 1, "name": "test"}', schema)
            True
            >>> TXUtils.validate_json_schema('{"id": "invalid", "name": "test"}', schema)
            False
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return False
        if not isinstance(data, dict):
            return False
        for key, schema_item in schema.items():
            if key not in data:
                return False
            value = data[key]
            expected_type = schema_item.type
            if not isinstance(value, expected_type):
                return False
        return True

    @staticmethod
    def read_text_file(file_path: str) -> str:
        """Read a text file and return its content as a UTF-8 decoded string.
        
        Args:
            file_path (str): Path to the text file to read.
            
        Returns:
            str: Content of the file as a UTF-8 string.
            
        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If the file cannot be read due to permissions or other I/O errors.
            
        Example:
            >>> content = TXUtils.read_text_file("/path/to/config.json")
            >>> print(content)  # File contents as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except Exception as e:
            raise IOError(f"Error reading file {file_path}: {str(e)}")
    @staticmethod
    def encrypt_password(password: str) -> str:
        """Hash a plaintext password using bcrypt with automatic salt generation.

        Uses bcrypt to securely hash passwords with a randomly generated salt.
        The resulting hash can be safely stored and used for password verification.

        Args:
            password (str): Plaintext password to hash.

        Returns:
            str: Bcrypt hash encoded as UTF-8 string, including salt information.
            
        Example:
            >>> hashed = TXUtils.encrypt_password("my_secure_password")
            >>> print(len(hashed))  # Typically 60 characters
            >>> print(hashed.startswith("$2b$"))  # True (bcrypt format)
            
        Note:
            Each call generates a different hash due to the random salt,
            even for the same input password.
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    @staticmethod
    def generate_uuid() -> str:
        """Generate a new RFC 4122 UUID4 as a string.
        
        Creates a random UUID (Universally Unique Identifier) version 4
        suitable for use as unique identifiers in the system.
        
        Returns:
            str: A new UUID4 string in standard format (e.g., "550e8400-e29b-41d4-a716-446655440000").
            
        Example:
            >>> uuid_str = TXUtils.generate_uuid()
            >>> print(len(uuid_str))  # 36 characters
            >>> print("-" in uuid_str)  # True (contains hyphens)
        """
        return str(u.uuid4())
        
    @staticmethod
    def generate_token() -> str:
        """Generate a new opaque token as a UUID4 string.
        
        Creates a random token suitable for authentication or session management.
        This is functionally identical to generate_uuid() but semantically
        indicates use as an authentication token.
        
        Returns:
            str: A new UUID4 string for use as an opaque token.
        """
        return str(u.uuid4())
    @staticmethod
    def validate_json(json_str: str) -> None:
        """Validate that a string is syntactically correct JSON.
        
        Parses the JSON string to ensure it conforms to valid JSON syntax.
        This method does not return the parsed data, only validates the format.
        
        Args:
            json_str (str): JSON string to validate.

        Raises:
            ValueError: If the string is not valid JSON, with details about the parsing error.
        """
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON string is invalid: {e}")
            
    @staticmethod
    def validate_float_precision(value: float, max_digit: int, max_decimals: int) -> None:
        """Validate that a float fits within precision and scale constraints.

        Checks that a float value doesn't exceed the specified total digit count
        and decimal places, which is useful for database storage validation.

        Args:
            value (float): Value to validate.
            max_digit (int): Maximum total digits (integer + fractional parts combined).
            max_decimals (int): Maximum digits after the decimal point.

        Raises:
            ValueError: If `value` is not a float, is out of the supported range, or exceeds the `max_digit` or `max_decimals` constraints.
        """
        if not isinstance(value, float):
            raise ValueError("Value must be a float.")
        if not -1e128 <= value <= 1e128:
            raise ValueError("Value is outside the supported float precision range.")
        
        str_value = str(abs(value))
        parts = str_value.split('.')        
        total_digits = len(parts[0])
        if len(parts) > 1:
            total_digits += len(parts[1])
            decimal_places = len(parts[1])
            if decimal_places > max_decimals:
                raise ValueError(f"Value cannot have more than {max_decimals} decimal places")
        if total_digits > max_digit:
            raise ValueError(f"Value cannot have more than {max_digit} total digits")            
    
class TXUserRole(Enum):
    """Enumeration of user roles for authorization and access control.
    
    Defines the available user roles in the system, determining
    what operations and resources a user can access.
    
    Attributes:
        ADMIN: Administrative user with full system access.
        STANDARD: Standard user with limited access permissions.
    """
    ADMIN = "ADMIN"
    STANDARD = "STANDARD"

@dataclass
class TXUserBase(ABC):
    """Abstract base class for user models with identity, credentials, and authorization.

    This class provides the foundation for user management, including secure password
    handling with bcrypt, role-based access control, profile information, and
    two-factor authentication support.

    Attributes:
        _uuid (str): Unique identifier for the user.
        _encrypted_password (str): Bcrypt-hashed password.
        _token (str): Authentication token for the user.
        _role (TXUserRole): User's role determining access permissions.
        _full_name (str, optional): User's full display name.
        _login (str, optional): User's login identifier.
        _enabled (bool): Whether the user account is active. Defaults to True.
        _creation_datetime (int, optional): Unix timestamp of account creation.
        _twofa_seed (str, optional): Seed for two-factor authentication.

    Example:
        >>> user = ConcreteUserClass()  # Assuming a concrete implementation
        >>> user.password = "secure_password"  # Automatically hashed
        >>> user.role = TXUserRole.ADMIN
        >>> user.full_name = "John Doe"
        >>> print(user.verify_password("secure_password"))  # True
    """

    _uuid: str
    _encrypted_password: str
    _token: str
    _role: TXUserRole
    _full_name: str = None
    _login: str = None
    _enabled: bool = True
    _creation_datetime: int = None
    _twofa_seed: str | None = None
    
    def __init__(self, uuid: Optional[str] = None, token: Optional[str] = None, encrypted_password: Optional[str] = None):
        """Initialize a new user instance.
        
        Args:
            uuid (str, optional): User UUID. If None, generates a new UUID.
            token (str, optional): Authentication token. If None, generates a new token.
            encrypted_password (str, optional): Pre-encrypted password hash.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self._token = TXUtils.generate_token() if token is None else token
        self._role = TXUserRole.STANDARD        
        self._encrypted_password = encrypted_password
        
    @property
    def uuid(self) -> str:
        """Get the user's unique identifier."""
        return self._uuid
        
    @property
    def password(self) -> str:
        """Get the encrypted password hash."""
        return self._encrypted_password
        
    @password.setter
    def password(self, value: str) -> None:
        """Set the user's password (automatically hashed with bcrypt).
        
        Args:
            value (str): Plain text password to hash and store.
        """
        self._encrypted_password = TXUtils.encrypt_password(value)
        
    def verify_password(self, password: str) -> bool:
        """Verify if the provided password matches the stored hash.
        
        Args:
            password (str): The plain text password to verify.
            
        Returns:
            bool: True if the password is correct, False otherwise.
            
        Example:
            >>> user.password = "my_password"
            >>> user.verify_password("my_password")  # True
            >>> user.verify_password("wrong_password")  # False
        """
        return bcrypt.checkpw(password.encode('utf-8'), self._encrypted_password.encode('utf-8'))
        
    @property
    def token(self) -> str:
        """Get the user's authentication token."""
        return self._token
        
    @property
    def role(self) -> TXUserRole:
        """Get the user's role for access control."""
        return self._role
        
    @role.setter
    def role(self, value: TXUserRole) -> None:
        """Set the user's role.
        
        Args:
            value (TXUserRole): The role to assign to the user.
        """
        self._role = value
        
    @property
    def full_name(self) -> str:
        """Get the user's full display name."""
        return self._full_name
        
    @full_name.setter
    def full_name(self, value: str) -> None:
        """Set the user's full display name.
        
        Args:
            value (str): The user's full name.
        """
        self._full_name = value
        
    @property
    def login(self) -> str:
        """Get the user's login identifier."""
        return self._login
        
    @login.setter
    def login(self, value: str) -> None:
        """Set the user's login identifier.
        
        Args:
            value (str): The login identifier (username, email, etc.).
        """
        self._login = value
        
    @property
    def twofa_seed(self) -> str | None:
        """Get the two-factor authentication seed."""
        return self._twofa_seed
        
    @twofa_seed.setter
    def twofa_seed(self, value: str | None) -> None:
        """Set the two-factor authentication seed.
        
        Args:
            value (str | None): The 2FA seed string, or None to disable 2FA.
            
        Raises:
            ValueError: If value is not a string or None.
        """
        if value is not None and not isinstance(value, str):
            raise ValueError("2fa_seed must be a string or None")
        self._twofa_seed = value
        
    @property
    def enabled(self) -> bool:
        """Get whether the user account is enabled."""
        return self._enabled
        
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set whether the user account is enabled.
        
        Args:
            value (bool): True to enable the account, False to disable.
        """
        self._enabled = value
    @property
    def creation_datetime(self) -> int:
        """Get the account creation timestamp."""
        return self._creation_datetime
        
    @creation_datetime.setter
    def creation_datetime(self, value: int) -> None:
        """Set the account creation timestamp.
        
        Args:
            value (int): Unix timestamp of when the account was created.
        """
        self._creation_datetime = value

@dataclass
class TXAssetBase(ABC):
    """Abstract base class for tangible assets tracked by wallets.
    
    This class defines the interface for assets that can be held in wallets,
    providing basic identification and naming properties that must be
    implemented by concrete asset classes.
    
    Attributes:
        _uuid (str): Unique identifier for the asset.
    """
    _uuid: str
    
    def __init__(self, uuid: Optional[str] = None):
        """Initialize a new asset instance.
        
        Args:
            uuid (str, optional): Asset UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
    @property
    def uuid(self) -> str:
        """Get the asset's unique identifier."""
        return self._uuid
        
    @property
    @abstractmethod
    def long_name(self) -> str:
        """Get the asset's full descriptive name.
        
        Returns:
            str: The complete name of the asset.
        """
        pass
        
    @long_name.setter
    @abstractmethod
    def long_name(self, value: str) -> None:
        """Set the asset's full descriptive name.
        
        Args:
            value (str): The complete name of the asset.
        """
        pass
        
    @property
    @abstractmethod
    def short_name(self) -> str:
        """Get the asset's abbreviated name or symbol.
        
        Returns:
            str: The short name or symbol of the asset.
        """
        pass
        
    @short_name.setter
    @abstractmethod
    def short_name(self, value: str) -> None:
        """Set the asset's abbreviated name or symbol.
        
        Args:
            value (str): The short name or symbol of the asset.
        """
        pass    

class TXCurrencyType(Enum):
    """Enumeration for classifying currencies as fiat or cryptocurrency.
    
    This enum is used to categorize different types of currencies
    in the system for proper handling and validation.
    
    Attributes:
        FIAT: Traditional government-issued currencies (USD, EUR, etc.).
        CRYPTO: Cryptocurrency or digital assets (Bitcoin, Ethereum, etc.).
    """
    FIAT = "FIAT"
    CRYPTO = "CRYPTO"

@dataclass
class TXCurrencyBase():
    """Concrete currency model with name, code, and type.
    
    This class represents a currency entity in the system, supporting both
    fiat currencies (USD, EUR, etc.) and cryptocurrencies (Bitcoin, Ethereum, etc.).
    Each currency has a unique identifier, descriptive names, and a classification type.
    
    Attributes:
        _uuid (str): Unique identifier for the currency.
        _long_name (str): Full descriptive name of the currency (e.g., "United States Dollar").
        _short_name (str): Short name or symbol of the currency (e.g., "USD", "BTC").
        _currency_type (TXCurrencyType): Classification as FIAT or CRYPTO currency.
        
    Example:
        >>> usd = TXCurrencyBase("United States Dollar", "USD", TXCurrencyType.FIAT)
        >>> btc = TXCurrencyBase("Bitcoin", "BTC", TXCurrencyType.CRYPTO)
        >>> print(usd.long_name)  # "United States Dollar"
        >>> print(btc.currency_type)  # TXCurrencyType.CRYPTO
    """
    _uuid: str
    _long_name: str = None
    _short_name: str = None
    _currency_type: TXCurrencyType = None
    
    def __init__(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: Optional[str] = None
    ):
        """Initialize a new currency instance.
        
        Args:
            long_name (str): Full descriptive name of the currency.
            short_name (str): Short name or symbol of the currency.
            currency_type (TXCurrencyType): Classification as FIAT or CRYPTO.
            uuid (str, optional): Currency UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.long_name = long_name
        self.short_name = short_name
        self.currency_type = currency_type
        
    @property
    def uuid(self) -> str:
        """Get the currency's unique identifier.
        
        Returns:
            str: The UUID of the currency.
        """
        return self._uuid
        
    @property
    def long_name(self) -> str:
        """Get the currency's full descriptive name.
        
        Returns:
            str: The full name of the currency.
        """
        return self._long_name
        
    @long_name.setter
    def long_name(self, value: str) -> None:
        """Set the currency's full descriptive name.
        
        Args:
            value (str): The full name of the currency.
        """
        self._long_name = value
        
    @property
    def short_name(self) -> str:
        """Get the currency's short name or symbol.
        
        Returns:
            str: The short name or symbol of the currency.
        """
        return self._short_name
        
    @short_name.setter
    def short_name(self, value: str) -> None:
        """Set the currency's short name or symbol.
        
        Args:
            value (str): The short name or symbol of the currency.
        """
        self._short_name = value
        
    @property
    def currency_type(self) -> TXCurrencyType:
        """Get the currency's classification type.
        
        Returns:
            TXCurrencyType: The type classification (FIAT or CRYPTO).
        """
        return self._currency_type
        
    @currency_type.setter
    def currency_type(self, value: TXCurrencyType) -> None:
        """Set the currency's classification type.
        
        Args:
            value (TXCurrencyType): The type classification (FIAT or CRYPTO).
            
        Raises:
            ValueError: If value is not a TXCurrencyType enum value.
        """
        if not isinstance(value, TXCurrencyType):
            raise ValueError(f"Currency type must be a TXCurrencyType enum value")
        self._currency_type = value

@dataclass
class TXExchangeDataSourceBase():
    """Abstract base class for exchange data sources providing currency exchange rates.
    
    This class defines the interface for data sources that can provide currency
    exchange rate information. Implementations can connect to various external
    APIs, databases, or other sources to retrieve real-time or historical
    exchange rate data.
    
    Attributes:
        _uuid (str): Unique identifier for the data source.
        _name (str): Human-readable name of the data source.
        _available_currency_types (Set[TXCurrencyType]): Set of currency types supported by this source.
        _default_for_types (Set[TXCurrencyType]): Set of currency types for which this is the default source.
        _notes (str): Additional notes or description about the data source.
        _connection_data_required (bool): Whether this source requires connection data for authentication.
        
    Example:
        >>> class CoinGeckoDataSource(TXExchangeDataSourceBase):
        ...     def get_currency_exchange(self, source, target, **kwargs):
        ...         # Implementation for CoinGecko API
        ...         pass
    """
    _uuid: str
    _name: str = None
    _available_currency_types: Set[TXCurrencyType] = None
    _default_for_types: Set[TXCurrencyType] = None
    _notes: str = None
    _connection_data_required: bool = False
    
    @staticmethod
    def get_connection_data_schema() -> dict[str, TXDataSchemaItem]:
        """Return schema describing required connection data for this data source.
        
        Defines the structure and types of connection data (API keys, endpoints, etc.) required to authenticate and connect to this data source.
        
        Returns:
            dict[str, TXDataSchemaItem]: Mapping of field names to TXDataSchemaItem descriptors that define the expected structure of connection_data.
            
        Example:
            >>> schema = MyDataSource.get_connection_data_schema()
            >>> print(schema)  # {"api_key": TXDataSchemaItem(name="API Key", type=str)}
        """
        return {}
        
    def __init__(self, uuid: Optional[str] = None):
        """Initialize a new exchange data source instance.
        
        Args:
            uuid (str, optional): Data source UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
    @abstractmethod
    def get_currency_exchange(self, currency_source: TXCurrencyBase, currency_target: TXCurrencyBase, user: Optional[TXUserBase] = None, datetime: Optional[int] = None, force_live_data: Optional[bool] = False) -> TXCurrencyExchangeBase:
        """Retrieve a currency exchange rate between two currencies at a specific datetime.
        
        Fetches the exchange rate from the source currency to the target currency.
        If datetime is None, the current datetime is used. The method should handle
        authentication using the user's connection data if required.

        Args:
            currency_source (TXCurrencyBase): The source currency to convert from.
            currency_target (TXCurrencyBase): The target currency to convert to.
            user (TXUserBase, optional): User for authentication/connection data access.
            datetime (int, optional): Unix timestamp for historical rates. If None, uses current time.
            force_live_data (bool, optional): Whether to force fetching live data instead of cached.

        Returns:
            TXCurrencyExchangeBase: Exchange rate object, or None if rate cannot be retrieved.
            
        Raises:
            ValueError: If currencies are not supported by this data source.
            ConnectionError: If unable to connect to the data source.
            
        Example:
            >>> usd = TXCurrencyBase("US Dollar", "USD", TXCurrencyType.FIAT)
            >>> eur = TXCurrencyBase("Euro", "EUR", TXCurrencyType.FIAT)
            >>> exchange = data_source.get_currency_exchange(usd, eur)
            >>> print(exchange.value)  # 0.85 (example rate)
        """
        pass
        
    @property
    def uuid(self) -> str:
        """Get the data source's unique identifier.
        
        Returns:
            str: The UUID of the data source.
        """
        return self._uuid
        
    @property
    def notes(self) -> str:
        """Get additional notes about the data source.
        
        Returns:
            str: Notes or description about the data source.
        """
        return self._notes
        
    @notes.setter
    def notes(self, value: str) -> None:
        """Set additional notes about the data source.
        
        Args:
            value (str): Notes or description about the data source.
        """
        self._notes = value
        
    @property
    def name(self) -> str:
        """Get the human-readable name of the data source.
        
        Returns:
            str: The name of the data source.
        """
        return self._name
        
    @property
    def available_currency_types(self) -> Set[TXCurrencyType]:
        """Get the set of currency types supported by this data source.
        
        Returns:
            Set[TXCurrencyType]: Set of supported currency types (FIAT, CRYPTO).
        """
        return self._available_currency_types
        
    @property
    def default_for_types(self) -> Set[TXCurrencyType]:
        """Get the set of currency types for which this is the default data source.
        
        Returns:
            Set[TXCurrencyType]: Set of currency types where this source is preferred.
        """
        return self._default_for_types
    @property
    def connection_data_required(self) -> bool:
        """Get whether this data source requires connection data for authentication.
        
        Returns:
            bool: True if connection data is required, False otherwise.
        """
        return self._connection_data_required

@dataclass
class TXCurrencyExchangeBase():
    """Represents a currency exchange rate between two currencies at a specific point in time.
    
    This class encapsulates exchange rate information including the source and target currencies, the exchange rate value, timestamp, and the data source that provided the rate. It supports precision validation for financial calculations.
    
    Attributes:
        _uuid (str): Unique identifier for the exchange rate record.
        _data_source (TXExchangeDataSourceBase): The data source that provided this rate.
        _currency_source (TXCurrencyBase): The source currency being converted from.
        _currency_target (TXCurrencyBase): The target currency being converted to.
        _value (float): The exchange rate value (how much of target currency equals 1 unit of source).
        _datetime (int): Unix timestamp when this exchange rate was valid.
        
    Example:
        >>> usd = TXCurrencyBase("US Dollar", "USD", TXCurrencyType.FIAT)
        >>> eur = TXCurrencyBase("Euro", "EUR", TXCurrencyType.FIAT)
        >>> exchange = TXCurrencyExchangeBase(usd, eur, 0.85, 1640995200)
        >>> print(f"1 {exchange.currency_source.short_name} = {exchange.value} {exchange.currency_target.short_name}")
        # "1 USD = 0.85 EUR"
    """
    _uuid: str
    _currency_source: TXCurrencyBase
    _currency_target: TXCurrencyBase
    _data_source: TXExchangeDataSourceBase = None
    _value: float = None
    _datetime: int = None
    
    def __init__(self, currency_source: TXCurrencyBase, currency_target: TXCurrencyBase, value: float, datetime: int, uuid: Optional[str] = None):
        """Initialize a new currency exchange rate instance.
        
        Args:
            currency_source (TXCurrencyBase): The source currency being converted from.
            currency_target (TXCurrencyBase): The target currency being converted to.
            value (float): The exchange rate value with precision validation.
            datetime (int): Unix timestamp when this rate was valid.
            uuid (str, optional): Exchange rate UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.currency_source = currency_source
        self.currency_target = currency_target
        self.value = value
        self.datetime = datetime
        
    @property
    def uuid(self) -> str:
        """Get the exchange rate's unique identifier.
        
        Returns:
            str: The UUID of the exchange rate record.
        """
        return self._uuid
        
    @property
    def value(self) -> float:
        """Get the exchange rate value.
        
        Returns:
            float: The exchange rate (target currency units per 1 source currency unit).
        """
        return self._value
        
    @value.setter
    def value(self, value: float) -> None:
        """Set the exchange rate value with precision validation.
        
        Validates that the exchange rate fits within the supported precision
        constraints (27 total digits, 15 decimal places) for financial calculations.
        
        Args:
            value (float): The exchange rate value to set.
            
        Raises:
            ValueError: If value exceeds precision constraints or is invalid.
        """
        TXUtils.validate_float_precision(value, 27, 15)
        self._value = value
        
    @property
    def datetime(self) -> int:
        """Get the timestamp when this exchange rate was valid.
        
        Returns:
            int: Unix timestamp of when the rate was recorded or valid.
        """
        return self._datetime
        
    @datetime.setter
    def datetime(self, value: int) -> None:
        """Set the timestamp when this exchange rate was valid.
        
        Args:
            value (int): Unix timestamp of when the rate was recorded or valid.
        """
        self._datetime = value
        
    @property
    def currency_source(self) -> TXCurrencyBase:
        """Get the source currency being converted from.
        
        Returns:
            TXCurrencyBase: The source currency in the exchange rate.
        """
        return self._currency_source
        
    @currency_source.setter
    def currency_source(self, value: TXCurrencyBase) -> None:
        """Set the source currency being converted from.
        
        Args:
            value (TXCurrencyBase): The source currency in the exchange rate.
        """
        self._currency_source = value
        
    @property
    def currency_target(self) -> TXCurrencyBase:
        """Get the target currency being converted to.
        
        Returns:
            TXCurrencyBase: The target currency in the exchange rate.
        """
        return self._currency_target
        
    @currency_target.setter
    def currency_target(self, value: TXCurrencyBase) -> None:
        """Set the target currency being converted to.
        
        Args:
            value (TXCurrencyBase): The target currency in the exchange rate.
        """
        self._currency_target = value
        
    @property
    def data_source(self) -> TXExchangeDataSourceBase:
        """Get the data source that provided this exchange rate.
        
        Returns:
            TXExchangeDataSourceBase: The data source that provided this rate.
        """
        return self._data_source
        
    @data_source.setter
    def data_source(self, value: TXExchangeDataSourceBase) -> None:
        """Set the data source that provided this exchange rate.
        
        Args:
            value (TXExchangeDataSourceBase): The data source that provided this rate.
        """
        self._data_source = value

@dataclass
class TXExchangeDataSourceConnectionDataBase():
    """Association between a user and an exchange data source with validated connection data.
    
    This class represents the relationship between a user and an exchange data source, storing the necessary connection credentials and configuration data required to authenticate and interact with the external data source. The connection data is validated against the data source's schema to ensure proper format.
    
    Attributes:
        _uuid (str): Unique identifier for this connection association.
        _user (TXUserBase): The user who owns this connection.
        _data_source (TXExchangeDataSourceBase): The exchange data source being connected to.
        _connection_data (str): JSON string containing connection credentials and configuration.
        
    Example:
        >>> user = MyUserClass()
        >>> data_source = MyCoinGeckoDataSource()
        >>> connection_data = '{"api_key": "your_api_key_here"}'
        >>> connection = TXExchangeDataSourceConnectionDataBase(user, data_source, connection_data)
        >>> print(connection.uuid)  # Generated UUID
    """
    _uuid: str
    _user: TXUserBase
    _data_source: TXExchangeDataSourceBase
    _connection_data: str
    
    def __init__(self, user: TXUserBase, data_source: TXExchangeDataSourceBase, connection_data: str, uuid: Optional[str] = None):
        """Initialize a new exchange data source connection.
        
        Args:
            user (TXUserBase): The user who owns this connection.
            data_source (TXExchangeDataSourceBase): The exchange data source to connect to.
            connection_data (str): JSON string with connection credentials, validated against data source schema.
            uuid (str, optional): Connection UUID. If None, generates a new UUID.
            
        Raises:
            ValueError: If connection_data doesn't match the data source's required schema.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self._user = user
        self._data_source = data_source
        self.connection_data = connection_data  # Use the setter to validate JSON
        
    @property
    def uuid(self) -> str:
        """Get the connection's unique identifier.
        
        Returns:
            str: The UUID of this connection association.
        """
        return self._uuid
        
    @property
    def user(self) -> TXUserBase:
        """Get the user who owns this connection.
        
        Returns:
            TXUserBase: The user associated with this connection.
        """
        return self._user
        
    @user.setter
    def user(self, value: TXUserBase) -> None:
        """Set the user who owns this connection.
        
        Args:
            value (TXUserBase): The user to associate with this connection.
        """
        self._user = value
        
    @property
    def data_source(self) -> TXExchangeDataSourceBase:
        """Get the exchange data source for this connection.
        
        Returns:
            TXExchangeDataSourceBase: The data source being connected to.
        """
        return self._data_source
        
    @data_source.setter
    def data_source(self, value: TXExchangeDataSourceBase) -> None:
        """Set the exchange data source for this connection.
        
        Args:
            value (TXExchangeDataSourceBase): The data source to connect to.
        """
        self._data_source = value
        
    @property
    def connection_data(self) -> str:
        """Get the connection data as a JSON string.
        
        Returns:
            str: JSON string containing connection credentials and configuration.
        """
        return self._connection_data
        
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        """Set the connection data with schema validation.
        
        Validates the connection data against the data source's required schema to ensure all necessary fields are present and properly formatted.
        
        Args:
            value (str): JSON string containing connection credentials and configuration.
            
        Raises:
            ValueError: If the connection data doesn't match the data source's schema.
        """
        if not TXUtils.validate_json_schema(value, self.data_source.get_connection_data_schema()):
            raise ValueError("Invalid connection_data schema")
        self._connection_data = value

class TXAssetType(Enum):
    """Enumeration of asset content types that a wallet may hold.
    
    This enum categorizes the different types of assets that can be stored
    and managed within wallets in the financial system. It helps distinguish between general assets and specific currency types.
    
    Attributes:
        ASSET: General tangible assets (stocks, bonds, commodities, etc.).
        CURRENCY_FIAT: Traditional government-issued currencies (USD, EUR, GBP, etc.).
        CURRENCY_CRYPTO: Cryptocurrency or digital assets (Bitcoin, Ethereum, etc.).
        
    Example:
        >>> wallet_type = TXAssetType.CURRENCY_CRYPTO
        >>> if wallet_type == TXAssetType.CURRENCY_CRYPTO:
        ...     print("This wallet holds cryptocurrency")
    """
    ASSET = "ASSET"
    CURRENCY_FIAT = "CURRENCY_FIAT"
    CURRENCY_CRYPTO = "CURRENCY_CRYPTO"

@dataclass
class TXFinancialHubBase(ABC):
    """Abstract base class for financial hubs that can create and persist transactions.
    
    This class defines the interface for financial hubs - systems that can execute and manage financial transactions. Financial hubs represent different trading platforms, exchanges, or financial institutions that can process various types of asset operations. Each hub defines what types of assets it can handle and requires specific connection data for authentication.
    
    Attributes:
        _uuid (str): Unique identifier for the financial hub.
        _name (str): Human-readable name of the financial hub.
        _allowed_operations (Set[TXAssetType]): Set of asset types this hub can handle.
        _notes (str): Additional notes or description about the hub.
        
    Example:
        >>> class MyExchangeHub(TXFinancialHubBase):
        ...     @staticmethod
        ...     def get_connection_data_schema():
        ...         return {"api_key": TXDataSchemaItem("API Key", str)}
        ...     def create_transaction(self, transaction):
        ...         # Implementation for creating transactions
        ...         return transaction
    """
    _uuid: str
    _name: str
    _allowed_operations: Set[TXAssetType]
    _notes: str
    
    @staticmethod
    @abstractmethod
    def get_connection_data_schema() -> dict[str, TXDataSchemaItem]:
        """Return schema describing required connection data for connecting to the hub.
        
        Defines the structure and types of connection data (API keys, endpoints, credentials, etc.) required to authenticate and connect to this financial hub. This schema is used to validate connection data when users set up their hub connections.
        
        Returns:
            dict[str, TXDataSchemaItem]: Mapping of field names to TXDataSchemaItem descriptors that define the expected structure of connection_data.
            
        Example:
            >>> schema = MyHub.get_connection_data_schema()
            >>> print(schema)  # {"api_key": TXDataSchemaItem(name="API Key", type=str), 
            #                   #  "secret": TXDataSchemaItem(name="Secret Key", type=str)}
        """
        pass
        
    def __init__(self, uuid: Optional[str] = None):
        """Initialize a new financial hub instance.
        
        Args:
            uuid (str, optional): Hub UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
    @abstractmethod
    def create_transaction(self, transaction: TXTransactionBase) -> TXTransactionBase:
        """Create and persist a transaction within the financial hub.
        
        Executes a transaction through this financial hub, handling the actual processing, validation, and persistence of the transaction. The implementation should interact with the hub's API or system to execute the transaction and return the updated transaction with any generated identifiers or status updates.

        Args:
            transaction (TXTransactionBase): Transaction to be created and executed.

        Returns:
            TXTransactionBase: The persisted transaction with updated status, identifiers, and any other information generated during execution.
            
        Raises:
            ValueError: If the transaction is invalid or cannot be processed.
            ConnectionError: If unable to connect to the financial hub.
            
        Example:
            >>> transaction = TXTransactionBase()
            >>> transaction.source_wallet = my_wallet
            >>> transaction.target_wallet = target_wallet
            >>> transaction.source_value = 100.0
            >>> result = hub.create_transaction(transaction)
            >>> print(result.status)  # TXTransStatus.COMPLETED or TXTransStatus.WORKING
        """
        pass
        
    @property
    def uuid(self) -> str:
        """Get the financial hub's unique identifier.
        
        Returns:
            str: The UUID of the financial hub.
        """
        return self._uuid
        
    @property
    def name(self) -> str:
        """Get the human-readable name of the financial hub.
        
        Returns:
            str: The name of the financial hub.
        """
        return self._name
        
    @name.setter
    def name(self, value: str) -> None:
        """Set the human-readable name of the financial hub.
        
        Args:
            value (str): The name of the financial hub.
        """
        self._name = value
        
    @property
    def allowed_operations(self) -> Set[TXAssetType]:
        """Get the set of asset types this hub can handle.
        
        Returns:
            Set[TXAssetType]: Set of asset types (ASSET, CURRENCY_FIAT, CURRENCY_CRYPTO) that this financial hub supports for transactions.
        """
        return self._allowed_operations
        
    @allowed_operations.setter
    def allowed_operations(self, value: Set[TXAssetType]) -> None:
        """Set the asset types this hub can handle.
        
        Args:
            value (Set[TXAssetType]): Set of asset types this hub supports.
        """
        self._allowed_operations = value
        
    @property
    def notes(self) -> str:
        """Get additional notes about the financial hub.
        
        Returns:
            str: Notes or description about the financial hub.
        """
        return self._notes
        
    @notes.setter
    def notes(self, value: str) -> None:
        """Set additional notes about the financial hub.
        
        Args:
            value (str): Notes or description about the financial hub.
        """
        self._notes = value

@dataclass
class TXFinancialHubConnectionDataBase():
    """Association between a user and a financial hub with validated connection data.
    
    This class represents the relationship between a user and a financial hub, storing the necessary connection credentials and configuration data required to authenticate and interact with the financial hub. The connection data is validated against the hub's schema to ensure proper format and completeness.
    
    Attributes:
        _uuid (str): Unique identifier for this connection association.
        _user (TXUserBase): The user who owns this connection.
        _financial_hub (TXFinancialHubBase): The financial hub being connected to.
        _connection_data (str): JSON string containing connection credentials and configuration.
        
    Example:
        >>> user = MyUserClass()
        >>> hub = MyExchangeHub()
        >>> connection_data = '{"api_key": "your_api_key", "secret": "your_secret"}'
        >>> connection = TXFinancialHubConnectionDataBase(user, hub, connection_data)
        >>> print(connection.uuid)  # Generated UUID
    """
    _uuid: str
    _user: TXUserBase
    _financial_hub: TXFinancialHubBase
    _connection_data: str
    
    def __init__(self, user: TXUserBase, financial_hub: TXFinancialHubBase, connection_data: str, uuid: Optional[str] = None):
        """Initialize a new financial hub connection.
        
        Args:
            user (TXUserBase): The user who owns this connection.
            financial_hub (TXFinancialHubBase): The financial hub to connect to.
            connection_data (str): JSON string with connection credentials, validated against hub schema.
            uuid (str, optional): Connection UUID. If None, generates a new UUID.
            
        Raises:
            ValueError: If connection_data doesn't match the financial hub's required schema.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid  
        self.user = user
        self.financial_hub = financial_hub
        self.connection_data = connection_data  # Use the setter to validate JSON
        
    @property
    def uuid(self) -> str:
        """Get the connection's unique identifier.
        
        Returns:
            str: The UUID of this connection association.
        """
        return self._uuid
        
    @property
    def user(self) -> TXUserBase:
        """Get the user who owns this connection.
        
        Returns:
            TXUserBase: The user associated with this connection.
        """
        return self._user
        
    @user.setter
    def user(self, value: TXUserBase) -> None:
        """Set the user who owns this connection.
        
        Args:
            value (TXUserBase): The user to associate with this connection.
        """
        self._user = value
        
    @property
    def financial_hub(self) -> TXFinancialHubBase:
        """Get the financial hub for this connection.
        
        Returns:
            TXFinancialHubBase: The financial hub being connected to.
        """
        return self._financial_hub
        
    @financial_hub.setter
    def financial_hub(self, value: TXFinancialHubBase) -> None:
        """Set the financial hub for this connection.
        
        Args:
            value (TXFinancialHubBase): The financial hub to connect to.
        """
        self._financial_hub = value
        
    @property
    def connection_data(self) -> str:
        """Get the connection data as a JSON string.
        
        Returns:
            str: JSON string containing connection credentials and configuration.
        """
        return self._connection_data
        
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        """Set the connection data with schema validation.
        
        Validates the connection data against the financial hub's required schema to ensure all necessary fields are present and properly formatted.
        
        Args:
            value (str): JSON string containing connection credentials and configuration.
            
        Raises:
            ValueError: If the connection data doesn't match the financial hub's schema.
        """
        if not TXUtils.validate_json_schema(value, self.financial_hub.get_connection_data_schema()):
            raise ValueError("Invalid connection_data schema")
        self._connection_data = value

@dataclass
class TXWalletBase():
    """Wallet model representing assets or currencies held within a financial hub.
    
    This class represents a wallet that holds a specific asset or currency within a financial hub. Wallets track both initial and current values with timestamps, and can store additional details and connection data specific to the wallet's implementation. Each wallet is associated with a user and a financial hub.

    Tracks initial and total values with timestamps, details data and connection data.
    
    Attributes:
        _uuid (str): Unique identifier for the wallet.
        _user (TXUserBase): The user who owns this wallet.
        _financial_hub (TXFinancialHubBase): The financial hub where this wallet exists.
        _asset (TXAssetBase, optional): The asset held in this wallet (if applicable).
        _currency (TXCurrencyBase): The currency denomination for this wallet.
        _name (str): Human-readable name for the wallet.
        _content_type (TXAssetType): Type of content this wallet holds.
        _initial_value (float, optional): Initial value when the wallet was created.
        _initial_value_datetime (int, optional): Unix timestamp of initial value recording.
        _total_value (float, optional): Current total value in the wallet.
        _total_value_datetime (int, optional): Unix timestamp of last value update.
        _details_data (str, optional): Additional JSON data specific to this wallet.
        _connection_data (str, optional): JSON connection data for wallet-specific operations.
        
    Example:
        >>> user = MyUserClass()
        >>> hub = MyExchangeHub()
        >>> usd = TXCurrencyBase("US Dollar", "USD", TXCurrencyType.FIAT)
        >>> wallet = TXWalletBase(user, hub, usd, "My USD Wallet", TXAssetType.CURRENCY_FIAT)
        >>> wallet.initial_value = 1000.0
        >>> wallet.total_value = 1250.0
    """
    _uuid: str
    _user: TXUserBase
    _financial_hub: TXFinancialHubBase
    _asset: TXAssetBase = None
    _currency: TXCurrencyBase
    _name: str
    _content_type: TXAssetType
    _initial_value: float = None
    _initial_value_datetime: int = None
    _total_value: float = None
    _total_value_datetime: int = None
    _details_data: str = None
    _connection_data: str = None
    
    def __init__(self, user: TXUserBase, financial_hub: TXFinancialHubBase, currency: TXCurrencyBase, name: str, content_type: TXAssetType, uuid: Optional[str] = None):
        """Initialize a new wallet instance.
        
        Args:
            user (TXUserBase): The user who owns this wallet.
            financial_hub (TXFinancialHubBase): The financial hub where this wallet exists.
            currency (TXCurrencyBase): The currency denomination for this wallet.
            name (str): Human-readable name for the wallet.
            content_type (TXAssetType): Type of content this wallet holds.
            uuid (str, optional): Wallet UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.user = user
        self.financial_hub = financial_hub
        self.currency = currency
        self.name = name
        self.content_type = content_type
        
    @property
    def uuid(self) -> str:
        """Get the wallet's unique identifier.
        
        Returns:
            str: The UUID of the wallet.
        """
        return self._uuid
        
    @property
    def user(self) -> TXUserBase:
        """Get the user who owns this wallet.
        
        Returns:
            TXUserBase: The user associated with this wallet.
        """
        return self._user
        
    @user.setter
    def user(self, value: TXUserBase) -> None:
        """Set the user who owns this wallet.
        
        Args:
            value (TXUserBase): The user to associate with this wallet.
        """
        self._user = value
        
    @property
    def financial_hub(self) -> TXFinancialHubBase:
        """Get the financial hub where this wallet exists.
        
        Returns:
            TXFinancialHubBase: The financial hub associated with this wallet.
        """
        return self._financial_hub
        
    @financial_hub.setter
    def financial_hub(self, value: TXFinancialHubBase) -> None:
        """Set the financial hub where this wallet exists.
        
        Args:
            value (TXFinancialHubBase): The financial hub to associate with this wallet.
        """
        self._financial_hub = value
        
    @property
    def asset(self) -> TXAssetBase:
        """Get the asset held in this wallet.
        
        Returns:
            TXAssetBase: The asset held in this wallet, or None if not applicable.
        """
        return self._asset
        
    @asset.setter
    def asset(self, value: TXAssetBase) -> None:
        """Set the asset held in this wallet.
        
        Args:
            value (TXAssetBase): The asset to be held in this wallet.
        """
        self._asset = value
        
    @property
    def currency(self) -> TXCurrencyBase:
        """Get the currency denomination for this wallet.
        
        Returns:
            TXCurrencyBase: The currency used for value calculations in this wallet.
        """
        return self._currency
        
    @currency.setter
    def currency(self, value: TXCurrencyBase) -> None:
        """Set the currency denomination for this wallet.
        
        Args:
            value (TXCurrencyBase): The currency to use for value calculations.
        """
        self._currency = value
        
    @property
    def name(self) -> str:
        """Get the human-readable name of the wallet.
        
        Returns:
            str: The display name of the wallet.
        """
        return self._name
        
    @name.setter
    def name(self, value: str) -> None:
        """Set the human-readable name of the wallet.
        
        Args:
            value (str): The display name for the wallet.
        """
        self._name = value
        
    @property
    def content_type(self) -> TXAssetType:
        """Get the type of content this wallet holds.
        
        Returns:
            TXAssetType: The asset type classification for this wallet's contents.
        """
        return self._content_type
        
    @content_type.setter
    def content_type(self, value: TXAssetType) -> None:
        """Set the type of content this wallet holds.
        
        Args:
            value (TXAssetType): The asset type classification for this wallet's contents.
            
        Raises:
            ValueError: If value is not a valid TXAssetType.
        """
        if not isinstance(value, TXAssetType):
            raise ValueError("content_type must be a TXAssetType")
        self._content_type = value
        
    @property
    def details_data(self) -> str:
        """Get additional details data for this wallet.
        
        Returns:
            str: JSON string containing wallet-specific details, or None if not set.
        """
        return self._details_data
        
    @details_data.setter
    def details_data(self, value: str) -> None:
        """Set additional details data for this wallet.
        
        Args:
            value (str): JSON string containing wallet-specific details.
            
        Raises:
            ValueError: If the JSON string is invalid or malformed.
        """
        TXUtils.validate_json(value)
        self._details_data = value
        
    @property
    def initial_value(self) -> float:
        """Get the initial value when the wallet was created.
        
        Returns:
            float: The initial value in the wallet's currency, or None if not set.
        """
        return self._initial_value
        
    @initial_value.setter
    def initial_value(self, value: float) -> None:
        """Set the initial value when the wallet was created.
        
        Args:
            value (float): The initial value in the wallet's currency.
            
        Raises:
            ValueError: If value exceeds precision constraints (25 digits, 10 decimals).
        """
        TXUtils.validate_float_precision(value, 25, 10)
        self._initial_value = value
        
    @property
    def initial_value_datetime(self) -> int:
        """Get the timestamp when the initial value was recorded.
        
        Returns:
            int: Unix timestamp of initial value recording, or None if not set.
        """
        return self._initial_value_datetime
        
    @initial_value_datetime.setter
    def initial_value_datetime(self, value: int) -> None:
        """Set the timestamp when the initial value was recorded.
        
        Args:
            value (int): Unix timestamp of initial value recording.
        """
        self._initial_value_datetime = value
        
    @property
    def total_value(self) -> float:
        """Get the current total value in the wallet.
        
        Returns:
            float: The current total value in the wallet's currency, or None if not set.
        """
        return self._total_value
        
    @total_value.setter
    def total_value(self, value: float) -> None:
        """Set the current total value in the wallet.
        
        Args:
            value (float): The current total value in the wallet's currency.
            
        Raises:
            ValueError: If value exceeds precision constraints (25 digits, 10 decimals).
        """
        TXUtils.validate_float_precision(value, 25, 10)
        self._total_value = value
        
    @property
    def total_value_datetime(self) -> int:
        """Get the timestamp when the total value was last updated.
        
        Returns:
            int: Unix timestamp of last value update, or None if not set.
        """
        return self._total_value_datetime
        
    @total_value_datetime.setter
    def total_value_datetime(self, value: int) -> None:
        """Set the timestamp when the total value was last updated.
        
        Args:
            value (int): Unix timestamp of last value update.
        """
        self._total_value_datetime = value
        
    @property
    def connection_data(self) -> str:
        """Get wallet-specific connection data.
        
        Returns:
            str: JSON string containing wallet-specific connection data, or None if not set.
        """
        return self._connection_data
        
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        """Set wallet-specific connection data.
        
        Args:
            value (str): JSON string containing wallet-specific connection data.
            
        Raises:
            ValueError: If the JSON string is invalid or malformed.
        """
        TXUtils.validate_json(value)
        self._connection_data = value

@dataclass
class TXBotBase():
    """Represents a trading bot instance with algorithm configuration and execution settings.
    
    This class encapsulates a trading bot that executes a specific algorithm with user-defined settings. It tracks the bot's metadata, algorithm information, execution state, and provides validation for algorithm settings.
    
    Attributes:
        _uuid (str): Unique identifier for the bot instance.
        _user (TXUserBase): The user who owns and operates this bot.
        _algo_uuid (str): UUID of the algorithm this bot executes.
        _name (str): Human-readable name for the bot instance.
        _algo_name (str): Name of the algorithm being executed.
        _algo_ver (str): Version of the algorithm being executed.
        _algo_settings (str): JSON string containing algorithm-specific settings.
        _annotations (str, optional): Additional notes or annotations about the bot.
        _active (bool): Whether the bot is currently active and running.
        _creation_datetime (int): Unix timestamp when the bot was created.
        
    Example:
        >>> user = MyUserClass()
        >>> bot = TXBotBase(
        ...     user=user,
        ...     algo_uuid="algo-123",
        ...     name="My Trading Bot",
        ...     algo_name="Simple Moving Average",
        ...     algo_ver="1.0.0",
        ...     algo_settings='{"period": 20, "threshold": 0.02}'
        ... )
        >>> bot.active = True
    """
    _uuid: str
    _user: TXUserBase
    _algo_uuid: str
    _name: str
    _algo_name: str
    _algo_ver: str
    _algo_settings: str
    _annotations: str | None = None
    _active: bool
    _creation_datetime: int
    
    def __init__(self, user: TXUserBase, algo_uuid: str, name: str, algo_name: str, algo_ver: str, algo_settings: str, uuid: Optional[str] = None):
        """Initialize a new trading bot instance.
        
        Args:
            user (TXUserBase): The user who owns this bot.
            algo_uuid (str): UUID of the algorithm to execute.
            name (str): Human-readable name for the bot.
            algo_name (str): Name of the algorithm.
            algo_ver (str): Version of the algorithm.
            algo_settings (str): JSON string with algorithm settings (validated).
            uuid (str, optional): Bot UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.user = user
        self.algo_uuid = algo_uuid
        self.name = name
        self.algo_name = algo_name
        self.algo_ver = algo_ver
        self.algo_settings = algo_settings  # Use the setter to validate JSON
        
    @property
    def uuid(self) -> str:
        """Get the bot's unique identifier.
        
        Returns:
            str: The UUID of the bot instance.
        """
        return self._uuid
        
    @property
    def user(self) -> TXUserBase:
        """Get the user who owns this bot.
        
        Returns:
            TXUserBase: The owner of the bot.
        """
        return self._user
        
    @user.setter
    def user(self, value: TXUserBase) -> None:
        """Set the user who owns this bot.
        
        Args:
            value (TXUserBase): The owner of the bot.
        """
        self._user = value
        
    @property
    def algo_settings(self) -> str:
        """Get the algorithm settings as a JSON string.
        
        Returns:
            str: JSON string containing algorithm-specific configuration.
        """
        return self._algo_settings
        
    @algo_settings.setter
    def algo_settings(self, value: str) -> None:
        """Set the algorithm settings with JSON validation.
        
        Args:
            value (str): JSON string containing algorithm settings.
            
        Raises:
            ValueError: If the JSON string is invalid or malformed.
        """
        TXUtils.validate_json(value)
        self._algo_settings = value
        
    @property
    def algo_uuid(self) -> str:
        """Get the UUID of the algorithm this bot executes.
        
        Returns:
            str: The algorithm's UUID.
        """
        return self._algo_uuid
        
    @algo_uuid.setter
    def algo_uuid(self, value: str) -> None:
        """Set the UUID of the algorithm this bot executes.
        
        Args:
            value (str): The algorithm's UUID.
        """
        self._algo_uuid = value
        
    @property
    def name(self) -> str:
        """Get the human-readable name of the bot.
        
        Returns:
            str: The bot's display name.
        """
        return self._name
        
    @name.setter
    def name(self, value: str) -> None:
        """Set the human-readable name of the bot.
        
        Args:
            value (str): The bot's display name.
        """
        self._name = value
        
    @property
    def algo_name(self) -> str:
        """Get the name of the algorithm being executed.
        
        Returns:
            str: The algorithm's name.
        """
        return self._algo_name
        
    @algo_name.setter
    def algo_name(self, value: str) -> None:
        """Set the name of the algorithm being executed.
        
        Args:
            value (str): The algorithm's name.
        """
        self._algo_name = value
        
    @property
    def algo_ver(self) -> str:
        """Get the version of the algorithm being executed.
        
        Returns:
            str: The algorithm's version string.
        """
        return self._algo_ver
        
    @algo_ver.setter
    def algo_ver(self, value: str) -> None:
        """Set the version of the algorithm being executed.
        
        Args:
            value (str): The algorithm's version string.
        """
        self._algo_ver = value
        
    @property
    def annotations(self) -> str | None:
        """Get additional annotations or notes about the bot.
        
        Returns:
            str | None: Annotations string, or None if no annotations are set.
        """
        return self._annotations
        
    @annotations.setter
    def annotations(self, value: str | None) -> None:
        """Set additional annotations or notes about the bot.
        
        Args:
            value (str | None): Annotations string, or None to clear annotations.
        """
        self._annotations = value
        
    @property
    def active(self) -> bool:
        """Get whether the bot is currently active and running.
        
        Returns:
            bool: True if the bot is active, False otherwise.
        """
        return self._active
        
    @active.setter
    def active(self, value: bool) -> None:
        """Set whether the bot is currently active and running.
        
        Args:
            value (bool): True to activate the bot, False to deactivate.
        """
        self._active = value
        
    @property
    def creation_datetime(self) -> int | None:
        """Get the timestamp when the bot was created.
        
        Returns:
            int | None: Unix timestamp of bot creation, or None if not set.
        """
        return self._creation_datetime
        
    @creation_datetime.setter
    def creation_datetime(self, value: int | None) -> None:
        """Set the timestamp when the bot was created.
        
        Args:
            value (int | None): Unix timestamp of bot creation, or None.
        """
        self._creation_datetime = value
class TXTransOperationalMode(Enum):
    """Enumeration of operational modes for financial transactions.
    
    This enum defines the different types of operations that can be performed in financial transactions, helping to categorize and process transactions according to their intended purpose and execution method.
    
    Attributes:
        ORDER_CREATION: Transaction involves creating trading orders (buy/sell orders).
        TRANSFER: Transaction involves transferring assets between wallets or accounts.
        OTHER: Transaction involves other types of operations not covered by specific modes.
        
    Example:
        >>> transaction.operational_mode = TXTransOperationalMode.ORDER_CREATION
        >>> if transaction.operational_mode == TXTransOperationalMode.TRANSFER:
        ...     print("Processing asset transfer")
    """
    ORDER_CREATION = 'ORDER CREATION'
    TRANSFER = 'TRANSFER'
    OTHER = 'OTHER'

class TXTransStatus(Enum):
    """Enumeration of possible transaction status values.
    
    This enum tracks the lifecycle status of financial transactions, from
    initiation through completion or failure. It provides a standardized
    way to monitor and report transaction progress.
    
    Attributes:
        WORKING: Transaction is currently being processed or executed.
        COMPLETED: Transaction has been successfully completed.
        CANCELED: Transaction was canceled before completion (by user or system).
        FAILED: Transaction failed due to an error or insufficient resources.
        OTHER: Transaction has a status not covered by the standard states.
        UNKNOWN: Transaction status cannot be determined or is not available.
        
    Example:
        >>> transaction.status = TXTransStatus.WORKING
        >>> while transaction.status == TXTransStatus.WORKING:
        ...     # Wait for transaction to complete
        ...     time.sleep(1)
        >>> if transaction.status == TXTransStatus.COMPLETED:
        ...     print("Transaction successful!")
    """
    WORKING = 'WORKING'
    COMPLETED = 'COMPLETED'
    CANCELED = 'CANCELED'
    FAILED = 'FAILED'
    OTHER = 'OTHER'
    UNKNOWN = 'UNKNOWN'

@dataclass
class TXTransactionBase():
    """Represents a financial transaction with comprehensive tracking and metadata.
    
    This class models a financial transaction that can involve transferring assets between wallets, creating orders, or other financial operations. It tracks the transaction's lifecycle, associated wallets, values, timing, and execution details.
    Transactions can be linked to trading bots and reference origin transactions for complex multi-step operations.
    
    Attributes:
        _uuid (str): Unique identifier for the transaction.
        _origin_transaction (TXTransactionBase, optional): Reference to the original transaction if this is a follow-up.
        _source_wallet (TXWalletBase, optional): Wallet from which assets are being transferred.
        _target_wallet (TXWalletBase, optional): Wallet to which assets are being transferred.
        _bot (TXBotBase, optional): Trading bot that initiated this transaction.
        _start_datetime (int, optional): Unix timestamp when the transaction started.
        _end_datetime (int, optional): Unix timestamp when the transaction completed.
        _operational_mode (TXTransOperationalMode, optional): Type of operation being performed.
        _source_value (float, optional): Amount being transferred from the source wallet.
        _target_value (float, optional): Amount being received in the target wallet.
        _status (TXTransStatus, optional): Current status of the transaction.
        _annotations (str, optional): Additional notes or comments about the transaction.
        _order (int): Sequence order for transaction processing (default: 0).
        
    Example:
        >>> source_wallet = TXWalletBase(user, hub, usd, "USD Wallet", TXAssetType.CURRENCY_FIAT)
        >>> target_wallet = TXWalletBase(user, hub, btc, "BTC Wallet", TXAssetType.CURRENCY_CRYPTO)
        >>> transaction = TXTransactionBase()
        >>> transaction.source_wallet = source_wallet
        >>> transaction.target_wallet = target_wallet
        >>> transaction.source_value = 1000.0
        >>> transaction.operational_mode = TXTransOperationalMode.ORDER_CREATION
        >>> transaction.status = TXTransStatus.WORKING
    """
    _uuid: str
    _origin_transaction: 'TXTransactionBase' | None = None
    _source_wallet: TXWalletBase | None = None
    _target_wallet: TXWalletBase | None = None
    _bot: TXBotBase | None = None
    _start_datetime: int | None = None
    _end_datetime: int | None = None
    _operational_mode: TXTransOperationalMode | None = None
    _source_value: float | None = None
    _target_value: float | None = None
    _status: TXTransStatus | None = None
    _annotations: str | None = None
    _order: int = 0
    
    def __init__(self, uuid: Optional[str] = None):
        """Initialize a new transaction instance.
        
        Args:
            uuid (str, optional): Transaction UUID. If None, generates a new UUID.
        """
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
    @property
    def uuid(self) -> str:
        """Get the transaction's unique identifier.
        
        Returns:
            str: The UUID of the transaction.
        """
        return self._uuid
        
    @property
    def origin_transaction(self) -> 'TXTransactionBase':
        """Get the original transaction that this transaction references.
        
        Returns:
            TXTransactionBase: The origin transaction, or None if this is an original transaction.
        """
        return self._origin_transaction
        
    @origin_transaction.setter
    def origin_transaction(self, value: 'TXTransactionBase') -> None:
        """Set the original transaction that this transaction references.
        
        Args:
            value (TXTransactionBase): The origin transaction to reference.
        """
        self._origin_transaction = value
        
    @property
    def source_wallet(self) -> TXWalletBase:
        """Get the wallet from which assets are being transferred.
        
        Returns:
            TXWalletBase: The source wallet, or None if not applicable.
        """
        return self._source_wallet
        
    @source_wallet.setter
    def source_wallet(self, value: TXWalletBase) -> None:
        """Set the wallet from which assets are being transferred.
        
        Args:
            value (TXWalletBase): The source wallet for the transaction.
        """
        self._source_wallet = value
        
    @property
    def target_wallet(self) -> TXWalletBase:
        """Get the wallet to which assets are being transferred.
        
        Returns:
            TXWalletBase: The target wallet, or None if not applicable.
        """
        return self._target_wallet
        
    @target_wallet.setter
    def target_wallet(self, value: TXWalletBase) -> None:
        """Set the wallet to which assets are being transferred.
        
        Args:
            value (TXWalletBase): The target wallet for the transaction.
        """
        self._target_wallet = value
        
    @property
    def bot(self) -> TXBotBase:
        """Get the trading bot that initiated this transaction.
        
        Returns:
            TXBotBase: The bot that created this transaction, or None if manually created.
        """
        return self._bot
        
    @bot.setter
    def bot(self, value: TXBotBase) -> None:
        """Set the trading bot that initiated this transaction.
        
        Args:
            value (TXBotBase): The bot that created this transaction.
        """
        self._bot = value
        
    @property
    def start_datetime(self) -> int:
        """Get the timestamp when the transaction started.
        
        Returns:
            int: Unix timestamp of transaction start, or None if not set.
        """
        return self._start_datetime
        
    @start_datetime.setter
    def start_datetime(self, value: int) -> None:
        """Set the timestamp when the transaction started.
        
        Args:
            value (int): Unix timestamp of transaction start.
        """
        self._start_datetime = value
        
    @property
    def end_datetime(self) -> int:
        """Get the timestamp when the transaction completed.
        
        Returns:
            int: Unix timestamp of transaction completion, or None if not completed.
        """
        return self._end_datetime
        
    @end_datetime.setter
    def end_datetime(self, value: int) -> None:
        """Set the timestamp when the transaction completed.
        
        Args:
            value (int): Unix timestamp of transaction completion.
        """
        self._end_datetime = value
        
    @property
    def operational_mode(self) -> TXTransOperationalMode:
        """Get the type of operation being performed.
        
        Returns:
            TXTransOperationalMode: The operational mode, or None if not set.
        """
        return self._operational_mode
        
    @operational_mode.setter
    def operational_mode(self, value: TXTransOperationalMode) -> None:
        """Set the type of operation being performed.
        
        Args:
            value (TXTransOperationalMode): The operational mode for this transaction.
        """
        self._operational_mode = value
        
    @property
    def source_value(self) -> float:
        """Get the amount being transferred from the source wallet.
        
        Returns:
            float: The source value amount, or None if not set.
        """
        return self._source_value
        
    @source_value.setter
    def source_value(self, value: float) -> None:
        """Set the amount being transferred from the source wallet.
        
        Args:
            value (float): The source value amount.
            
        Raises:
            ValueError: If value exceeds precision constraints (25 digits, 10 decimals).
        """
        TXUtils.validate_float_precision(value, 25, 10)
        self._source_value = value
        
    @property
    def target_value(self) -> float:
        """Get the amount being received in the target wallet.
        
        Returns:
            float: The target value amount, or None if not set.
        """
        return self._target_value
        
    @target_value.setter
    def target_value(self, value: float) -> None:
        """Set the amount being received in the target wallet.
        
        Args:
            value (float): The target value amount.
            
        Raises:
            ValueError: If value exceeds precision constraints (25 digits, 10 decimals).
        """
        TXUtils.validate_float_precision(value, 25, 10)
        self._target_value = value
        
    @property
    def status(self) -> TXTransStatus:
        """Get the current status of the transaction.
        
        Returns:
            TXTransStatus: The transaction status, or None if not set.
        """
        return self._status
        
    @status.setter
    def status(self, value: TXTransStatus) -> None:
        """Set the current status of the transaction.
        
        Args:
            value (TXTransStatus): The transaction status.
        """
        self._status = value
        
    @property
    def annotations(self) -> str | None:
        """Get additional notes or comments about the transaction.
        
        Returns:
            str | None: Annotations string, or None if no annotations are set.
        """
        return self._annotations
        
    @annotations.setter
    def annotations(self, value: str | None) -> None:
        """Set additional notes or comments about the transaction.
        
        Args:
            value (str | None): Annotations string, or None to clear annotations.
        """
        self._annotations = value
        
    @property
    def order(self) -> int:
        """Get the sequence order for transaction processing.
        
        Returns:
            int: The processing order number.
        """
        return self._order
        
    @order.setter
    def order(self, value: int) -> None:
        """Set the sequence order for transaction processing.
        
        Args:
            value (int): The processing order number.
        """
        self._order = value
