from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Set
import uuid as u
import bcrypt
import json

class TXUtils():

    @staticmethod
    def read_text_file(file_path: str) -> str:
        """
        Reads a text file and returns its content as a UTF-8 decoded string.
        
        Args:
            file_path (str): Path to the text file
            
        Returns:
            str: Content of the file as a UTF-8 string
            
        Raises:
            FileNotFoundError: If the file does not exist
            IOError: If the file cannot be read
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
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    @staticmethod
    def generate_uuid() -> str:
        return str(u.uuid4())
    @staticmethod
    def generate_token() -> str:
        return str(u.uuid4())
    @staticmethod
    def validate_json(json_str: str) -> None:
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON string is invalid: {str(e)}")
    @staticmethod
    def validate_float_precision(value: float, max_digit: int, max_decimals: int) -> None:
        if not isinstance(value, float):
            raise ValueError("Value must be a float")
        if not -1e128 <= value <= 1e128:
            raise ValueError("Value must be within the float precision range")
        # Validate total digits and decimal places
        str_value = str(abs(value))
        parts = str_value.split('.')        
        total_digits = len(parts[0])  # Integer part
        if len(parts) > 1:
            total_digits += len(parts[1])  # Decimal part
            decimal_places = len(parts[1])
            if decimal_places > max_decimals:
                raise ValueError(f"Value cannot have more than {max_decimals} decimal places")
        if total_digits > max_digit:
            raise ValueError(f"Value cannot have more than {max_digit} total digits")            
    
class TXUserRole(Enum):
    ADMIN = "ADMIN"
    STANDARD = "STANDARD"

class TXUserBase(ABC):
    _uuid: str
    _encrypted_password: str
    _token: str
    _role: TXUserRole
    _full_name: str = None
    _login: str = None
    _enabled: bool = True
    _creation_datetime: int = None
    _twofa_seed: str | None = None
    def __init__(self, uuid: str = None, token: str = None, encrypted_password: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self._token = TXUtils.generate_token() if token is None else token
        self._role = TXUserRole.STANDARD        
        self._encrypted_password = encrypted_password
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def password(self) -> str:
        return self._encrypted_password
    @password.setter
    def password(self, value: str) -> None:
        # Generate a salt and create the password hash using bcrypt
        self._encrypted_password = TXUtils.encrypt_password(value)    
    def verify_password(self, password: str) -> bool:
        """
        Verifies if the provided password matches the stored hash.
        
        Args:
            password (str): The plain text password to verify
            
        Returns:
            bool: True if the password is correct, False otherwise
        """
        return bcrypt.checkpw(password.encode('utf-8'), self._encrypted_password.encode('utf-8'))
    @property
    def token(self) -> str:
        return self._token
    @property
    def role(self) -> TXUserRole:
        return self._role
    @role.setter
    def role(self, value: TXUserRole) -> None:
        self._role = value
    @property
    def full_name(self) -> str:
        return self._full_name
    @full_name.setter
    def full_name(self, value: str) -> None:
        self._full_name = value
    @property
    def login(self) -> str:
        return self._login
    @login.setter
    def login(self, value: str) -> None:
        self._login = value    
    @property
    def twofa_seed(self) -> str | None:
        return self._twofa_seed
    @twofa_seed.setter
    def twofa_seed(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise ValueError("2fa_seed must be a string or None")
        self._twofa_seed = value
    @property
    def enabled(self) -> bool:
        return self._enabled
    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
    @property
    def creation_datetime(self) -> int:
        return self._creation_datetime
    @creation_datetime.setter
    def creation_datetime(self, value: int) -> None:
        self._creation_datetime = value

class TXAssetBase(ABC):
    _uuid: str
    def __init__(self, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    @abstractmethod
    def long_name(self) -> str:
        pass
    @long_name.setter
    @abstractmethod
    def long_name(self, value: str) -> None:
        pass
    @property
    @abstractmethod
    def short_name(self) -> str:
        pass
    @short_name.setter
    @abstractmethod
    def short_name(self, value: str) -> None:
        pass    

class TXCurrencyType(Enum):
    FIAT = "FIAT"
    CRYPTO = "CRYPTO"

class TXCurrencyBase():
    _uuid: str
    _long_name: str = None
    _short_name: str = None
    _currency_type: TXCurrencyType = None
    def __init__(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: str = None
    ):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.long_name = long_name
        self.short_name = short_name
        self.currency_type = currency_type
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def long_name(self) -> str:
        return self._long_name
    @long_name.setter
    def long_name(self, value: str) -> None:
        self._long_name = value
    @property
    def short_name(self) -> str:
        return self._short_name
    @short_name.setter
    def short_name(self, value: str) -> None:
        self._short_name = value
    @property
    def currency_type(self) -> TXCurrencyType:
        return self._currency_type
    @currency_type.setter
    def currency_type(self, value: TXCurrencyType) -> None:
        if not isinstance(value, TXCurrencyType):
            raise ValueError(f"Currency type must be a TXCurrencyType enum value")
        self._currency_type = value

class TXExchangeDataSourceBase():
    _uuid: str
    _name: str = None
    _avaiable_currency_types: Set[TXCurrencyType] = None
    _default_for_types: Set[TXCurrencyType] = None
    _notes: str = None
    _connection_data_required: bool = None
    def __init__(self, name: str, avaiable_currency_types: Set[TXCurrencyType], connection_data_required: bool, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.name = name
        self.avaiable_currency_types = avaiable_currency_types
        self.connection_data_required = connection_data_required
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def name(self) -> str:
        return self._name
    @name.setter
    def name(self, value: str) -> None:
        self._name = value    
    @property
    def avaiable_currency_types(self) -> Set[TXCurrencyType]:
        return self._avaiable_currency_types
    @avaiable_currency_types.setter
    def avaiable_currency_types(self, value: Set[TXCurrencyType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXCurrencyType) for item in value)):
            raise ValueError(f"Currency types must be a set of TXCurrencyType enum values")
        self._avaiable_currency_types = value
    @property
    def default_for_types(self) -> Set[TXCurrencyType]:
        return self._default_for_types
    @default_for_types.setter
    def default_for_types(self, value: Set[TXCurrencyType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXCurrencyType) for item in value)):
            raise ValueError(f"Currency types must be a set of TXCurrencyType enum values")
        self._default_for_types = value
    @property
    def connection_data_required(self) -> bool:
        return self._connection_data_required
    @connection_data_required.setter
    def connection_data_required(self, value: bool) -> None:
        self._connection_data_required = value
    @property
    def notes(self) -> str:
        return self._notes
    @notes.setter
    def notes(self, value: str) -> None:
        self._notes = value

class TXCurrencyExchangeBase():
    _uuid: str
    _data_source: TXExchangeDataSourceBase = None
    _currency_source: TXCurrencyBase
    _currency_target: TXCurrencyBase
    _value: float = None
    _datetime: int = None
    def __init__(self, currency_source: TXCurrencyBase, currency_target: TXCurrencyBase, value: float, datetime: int, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.currency_source = currency_source
        self.currency_target = currency_target
        self.value = value
        self.datetime = datetime
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def value(self) -> float:
        return self._value
    @value.setter
    def value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 13)
        self._value = value
    @property
    def datetime(self) -> int:
        return self._datetime
    @datetime.setter
    def datetime(self, value: int) -> None:
        self._datetime = value
    @property
    def currency_source(self) -> TXCurrencyBase:
        return self._currency_source
    @currency_source.setter
    def currency_source(self, value: TXCurrencyBase) -> None:
        self._currency_source = value
    @property
    def currency_target(self) -> TXCurrencyBase:
        return self._currency_target
    @currency_target.setter
    def currency_target(self, value: TXCurrencyBase) -> None:
        self._currency_target = value
    @property
    def data_source(self) -> TXExchangeDataSourceBase:
        return self._data_source
    @data_source.setter
    def data_source(self, value: TXExchangeDataSourceBase) -> None:
        self._data_source = value

class TXExchangeDataSourceConnectionDataBase():
    _uuid: str
    _user: TXUserBase
    _data_source: TXExchangeDataSourceBase
    _connection_data: str
    def __init__(self, user: TXUserBase, data_source: TXExchangeDataSourceBase, connection_data: str, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self._user = user
        self._data_source = data_source
        self.connection_data = connection_data  # Use the setter to validate JSON
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def user(self) -> TXUserBase:
        return self._user
    @user.setter
    def user(self, value: TXUserBase) -> None:
        self._user = value
    @property
    def data_source(self) -> TXExchangeDataSourceBase:
        return self._data_source
    @data_source.setter
    def data_source(self, value: TXExchangeDataSourceBase) -> None:
        self._data_source = value
    @property
    def connection_data(self) -> str:
        return self._connection_data
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._connection_data = value

class TXAssetType(Enum):
    ASSET = "ASSET"
    CURRENCY_FIAT = "CURRENCY_FIAT"
    CURRENCY_CRYPTO = "CURRENCY_CRYPTO"

class TXFinancialHubBase():
    _uuid: str
    _name: str
    _allowed_operations: Set[TXAssetType]
    _notes: str
    def __init__(self, name: str, allowed_operations: Set[TXAssetType], uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.name = name
        self.allowed_operations = allowed_operations
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def name(self) -> str:
        return self._name
    @name.setter
    def name(self, value: str) -> None:
        self._name = value
    @property
    def allowed_operations(self) -> Set[TXAssetType]:
        return self._allowed_operations
    @allowed_operations.setter
    def allowed_operations(self, value: Set[TXAssetType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXAssetType) for item in value)):
            raise ValueError(f"allowed_operations must be a set of TXAssetType enum values")
        self._allowed_operations = value
    @property
    def notes(self) -> str:
        return self._notes
    @notes.setter
    def notes(self, value: str) -> None:
        self._notes = value

class TXFinancialHubConnectionDataBase():
    _uuid: str
    _user: TXUserBase
    _financial_hub: TXFinancialHubBase
    _connection_data: str
    def __init__(self, user: TXUserBase, financial_hub: TXFinancialHubBase, connection_data: str, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
        self.user = user
        self.financial_hub = financial_hub
        self.connection_data = connection_data  # Use the setter to validate JSON
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def user(self) -> TXUserBase:
        return self._user
    @user.setter
    def user(self, value: TXUserBase) -> None:
        self._user = value
    @property
    def financial_hub(self) -> TXFinancialHubBase:
        return self._financial_hub
    @financial_hub.setter
    def financial_hub(self, value: TXFinancialHubBase) -> None:
        self._financial_hub = value
    @property
    def connection_data(self) -> str:
        return self._connection_data
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._connection_data = value

class TXWalletBase():
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
    def __init__(self, user: TXUserBase, financial_hub: TXFinancialHubBase, currency: TXCurrencyBase, name: str, content_type: TXAssetType, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.user = user
        self.financial_hub = financial_hub
        self.currency = currency
        self.name = name
        self.content_type = content_type
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def user(self) -> TXUserBase:
        return self._user
    @user.setter
    def user(self, value: TXUserBase) -> None:
        self._user = value
    @property
    def financial_hub(self) -> TXFinancialHubBase:
        return self._financial_hub
    @financial_hub.setter
    def financial_hub(self, value: TXFinancialHubBase) -> None:
        self._financial_hub = value
    @property
    def asset(self) -> TXAssetBase:
        return self._asset
    @asset.setter
    def asset(self, value: TXAssetBase) -> None:
        self._asset = value
        pass
    @property
    def currency(self) -> TXCurrencyBase:
        return self._currency
    @currency.setter
    def currency(self, value: TXCurrencyBase) -> None:
        self._currency = value
        pass
    @property
    def name(self) -> str:
        return self._name
    @name.setter
    def name(self, value: str) -> None:
        self._name = value
    @property
    def content_type(self) -> TXAssetType:
        return self._content_type
    @content_type.setter
    def content_type(self, value: TXAssetType) -> None:
        if not isinstance(value, TXAssetType):
            raise ValueError("content_type must be a TXAssetType")
        self._content_type = value
    @property
    def details_data(self) -> str:
        return self._details_data
    @details_data.setter
    def details_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._details_data = value
    @property
    def initial_value(self) -> float:
        return self._initial_value
    @initial_value.setter
    def initial_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        self._initial_value = value
    @property
    def initial_value_datetime(self) -> int:
        return self._initial_value_datetime
    @initial_value_datetime.setter
    def initial_value_datetime(self, value: int) -> None:
        self._initial_value_datetime = value
    @property
    def total_value(self) -> float:
        return self._total_value
    @total_value.setter
    def total_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        self._total_value = value
    @property
    def total_value_datetime(self) -> int:
        return self._total_value_datetime
    @total_value_datetime.setter
    def total_value_datetime(self, value: int) -> None:
        self._total_value_datetime = value  
    @property
    def connection_data(self) -> str:
        return self._connection_data
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._connection_data = value

class TXBotBase():
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
    def __init__(self, user: TXUserBase, algo_uuid: str, name: str, algo_name: str, algo_ver: str, algo_settings: str, uuid: str = None):
        self._uuid = TXUtils.generate_uuid() if uuid is None else uuid
        self.user = user
        self.algo_uuid = algo_uuid
        self.name = name
        self.algo_name = algo_name
        self.algo_ver = algo_ver
        self.algo_settings = algo_settings  # Use the setter to validate JSON
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def user(self) -> TXUserBase:
        return self._user
    @user.setter
    def user(self, value: TXUserBase) -> None:
        self._user = value
    @property
    def algo_settings(self) -> str:
        return self._algo_settings
    @algo_settings.setter
    def algo_settings(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._algo_settings = value
    @property
    def algo_uuid(self) -> str:
        return self._algo_uuid
    @algo_uuid.setter
    def algo_uuid(self, value: str) -> None:
        self._algo_uuid = value
    @property
    def name(self) -> str:
        return self._name
    @name.setter
    def name(self, value: str) -> None:
        self._name = value
    @property
    def algo_name(self) -> str:
        return self._algo_name
    @algo_name.setter
    def algo_name(self, value: str) -> None:
        self._algo_name = value
    @property
    def algo_ver(self) -> str:
        return self._algo_ver
    @algo_ver.setter
    def algo_ver(self, value: str) -> None:
        self._algo_ver = value
    @property
    def annotations(self) -> str | None:
        return self._annotations
    @annotations.setter
    def annotations(self, value: str | None) -> None:
        self._annotations = value
    @property
    def active(self) -> bool:
        return self._active
    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
    @property
    def creation_datetime(self) -> int | None:
        return self._creation_datetime
    @creation_datetime.setter
    def creation_datetime(self, value: int | None) -> None:
        self._creation_datetime = value
class TXTransOperationalMode(Enum):
    ORDER_CREATION = 'ORDER CREATION'
    TRANSFER = 'TRANSFER'
    OTHER = 'OTHER'

class TXTransStatus(Enum):
    WORKING = 'WORKING'
    COMPLETED = 'COMPLETED'
    CANCELED = 'CANCELED'
    FAILED = 'FAILED'
    OTHER = 'OTHER'
    UNKNOWN = 'UNKNOWN'

class TXTransactionBase():
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
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    def origin_transaction(self) -> 'TXTransactionBase':
        return self._origin_transaction
    @origin_transaction.setter
    def origin_transaction(self, value: 'TXTransactionBase') -> None:
        self._origin_transaction = value
    @property
    def source_wallet(self) -> TXWalletBase:
        return self._source_wallet
    @source_wallet.setter
    def source_wallet(self, value: TXWalletBase) -> None:
        self._source_wallet = value
    @property
    def target_wallet(self) -> TXWalletBase:
        return self._target_wallet
    @target_wallet.setter
    def target_wallet(self, value: TXWalletBase) -> None:
        self._target_wallet = value
    @property
    def bot(self) -> TXBotBase:
        return self._bot
    @bot.setter
    def bot(self, value: TXBotBase) -> None:
        self._bot = value
    @property
    def start_datetime(self) -> int:
        return self._start_datetime
    @start_datetime.setter
    def start_datetime(self, value: int) -> None:
        self._start_datetime = value
    @property
    def end_datetime(self) -> int:
        return self._end_datetime
    @end_datetime.setter
    def end_datetime(self, value: int) -> None:
        self._end_datetime = value
    @property
    def operational_mode(self) -> TXTransOperationalMode:
        return self._operational_mode
    @operational_mode.setter
    def operational_mode(self, value: TXTransOperationalMode) -> None:
        self._operational_mode = value
    @property
    def source_value(self) -> float:
        return self._source_value
    @source_value.setter
    def source_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        self._source_value = value
    @property
    def target_value(self) -> float:
        return self._target_value
    @target_value.setter
    def target_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        self._target_value = value
    @property
    def status(self) -> TXTransStatus:
        return self._status
    @status.setter
    def status(self, value: TXTransStatus) -> None:
        self._status = value
    @property
    def annotations(self) -> str | None:
        return self._annotations
    @annotations.setter
    def annotations(self, value: str | None) -> None:
        self._annotations = value
    @property
    def order(self) -> int:
        return self._order
    @order.setter
    def order(self, value: int) -> None:
        self._order = value
