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
        self._uuid = str(u.uuid4()) if uuid is None else uuid
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

class TXCurrencyBase(ABC):
    _uuid: str
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
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
    @property
    @abstractmethod
    def currency_type(self) -> TXCurrencyType:
        pass
    @currency_type.setter
    @abstractmethod
    def currency_type(self, value: TXCurrencyType) -> None:
        if not isinstance(value, TXCurrencyType):
            raise ValueError(f"Currency type must be a TXCurrencyType enum value")
        pass

class TXExchangeDataSourceBase():
    _uuid: str
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    @name.setter
    @abstractmethod
    def name(self, value: str) -> None:
        pass
    @property
    @abstractmethod
    def avaiable_currency_types(self) -> Set[TXCurrencyType]:
        pass
    @avaiable_currency_types.setter
    @abstractmethod
    def avaiable_currency_types(self, value: Set[TXCurrencyType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXCurrencyType) for item in value)):
            raise ValueError(f"Currency types must be a set of TXCurrencyType enum values")
        pass
    @property
    @abstractmethod
    def default_for_types(self) -> Set[TXCurrencyType]:
        pass
    @default_for_types.setter
    @abstractmethod
    def default_for_types(self, value: Set[TXCurrencyType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXCurrencyType) for item in value)):
            raise ValueError(f"Currency types must be a set of TXCurrencyType enum values")
        pass
    @property
    @abstractmethod
    def connection_data_required(self) -> bool:
        pass
    @connection_data_required.setter
    @abstractmethod
    def connection_data_required(self, value: bool) -> None:
        pass

class TXCurrencyExchangeBase(ABC):
    _uuid: str
    _data_source: TXExchangeDataSourceBase
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
        self.data_source = None       
    @property
    def uuid(self) -> str:
        return self._uuid
    @property
    @abstractmethod
    def source(self) -> TXCurrencyBase:
        pass
    @source.setter
    @abstractmethod
    def source(self, value: TXCurrencyBase) -> None:
        pass
    @property
    @abstractmethod
    def target(self) -> TXCurrencyBase:
        pass
    @target.setter
    @abstractmethod
    def target(self, value: TXCurrencyBase) -> None:
        pass
    @property
    @abstractmethod
    def data_source(self) -> TXExchangeDataSourceBase:
        return self._data_source
    @data_source.setter
    @abstractmethod
    def data_source(self, value: TXExchangeDataSourceBase) -> None:
        self._data_source = value
    @property
    @abstractmethod
    def value(self) -> float:
        pass
    @value.setter
    @abstractmethod 
    def value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 13)
        pass
    @property
    @abstractmethod
    def datetime(self) -> int:
        pass    
    @datetime.setter
    @abstractmethod
    def datetime(self, value: int) -> None:
        pass

class TXExchangeDataSourceConnectionDataBase():
    _uuid: str
    _user: TXUserBase
    _data_source: TXExchangeDataSourceBase
    _connection_data: str
    def __init__(self, user: TXUserBase, data_source: TXExchangeDataSourceBase, connection_data: str, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
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

class TXFinancialHubBase(ABC):
    _uuid: str
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    @name.setter
    @abstractmethod
    def name(self, value: str) -> None:
        pass
    @property
    @abstractmethod
    def allowed_operations(self) -> Set[TXAssetType]:
        pass
    @allowed_operations.setter
    @abstractmethod
    def allowed_operations(self, value: Set[TXAssetType]) -> None:
        if (not isinstance(value, set)) or (not all(isinstance(item, TXAssetType) for item in value)):
            raise ValueError(f"allowed_operations must be a set of TXAssetType enum values")
        pass

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

class TXWalletBase(ABC):
    _uuid: str
    _user: TXUserBase
    _financial_hub: TXFinancialHubBase
    _asset: TXAssetBase
    _currency: TXCurrencyBase
    _details_data: str
    _connection_data: str
    def __init__(self, user: TXUserBase, financial_hub: TXFinancialHubBase, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
        self.user = user
        self.financial_hub = financial_hub
        self.asset = None
        self.currency = None
        self.connection_data = None
        self.details_data = None
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
    @abstractmethod
    def asset(self) -> TXAssetBase:
        return self._asset
    @asset.setter
    @abstractmethod
    def asset(self, value: TXAssetBase) -> None:
        self._asset = value
        pass
    @property
    @abstractmethod
    def currency(self) -> TXCurrencyBase:
        return self._currency
    @currency.setter
    @abstractmethod
    def currency(self, value: TXCurrencyBase) -> None:
        self._currency = value
        pass
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    @name.setter
    @abstractmethod
    def name(self, value: str) -> None:
        pass
    @property
    def details_data(self) -> str:
        return self._details_data
    @details_data.setter
    def details_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._details_data = value
    @property
    @abstractmethod
    def initial_value(self) -> float:
        pass
    @initial_value.setter
    @abstractmethod
    def initial_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        pass
    @property
    @abstractmethod
    def initial_value_datetime(self) -> int:
        pass
    @initial_value_datetime.setter
    @abstractmethod
    def initial_value_datetime(self, value: int) -> None:
        pass
    @property
    @abstractmethod
    def total_value(self) -> float:
        pass
    @total_value.setter
    @abstractmethod
    def total_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        pass
    @property
    @abstractmethod
    def total_value_datetime(self) -> int:
        pass
    @total_value_datetime.setter
    @abstractmethod
    def total_value_datetime(self, value: int) -> None:
        pass
    @property
    def connection_data(self) -> str:
        return self._connection_data
    @connection_data.setter
    def connection_data(self, value: str) -> None:
        TXUtils.validate_json(value)
        self._connection_data = value

class TXBotBase(ABC):
    _uuid: str
    _user: TXUserBase
    _algo_uuid: str
    _name: str
    _algo_ver: str
    _algo_settings: str
    def __init__(self, user: TXUserBase, algo_uuid: str, name: str, algo_ver: str, algo_settings: str, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
        self.user = user
        self.algo_uuid = algo_uuid
        self.name = name
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
    def algo_ver(self) -> str:
        return self._algo_ver
    @algo_ver.setter
    def algo_ver(self, value: str) -> None:
        self._algo_ver = value
    @property
    @abstractmethod
    def annotations(self) -> str:
        pass
    @annotations.setter
    @abstractmethod
    def annotations(self, value: str) -> None:
        pass
    @property
    @abstractmethod
    def active(self) -> bool:
        pass
    @active.setter
    @abstractmethod
    def active(self, value: bool) -> None:
        pass
    @property
    @abstractmethod
    def deleted(self) -> bool:
        pass
    @deleted.setter
    @abstractmethod
    def deleted(self, value: bool) -> None:
        pass
    @property
    @abstractmethod
    def creation_datetime(self) -> int:
        pass
    @creation_datetime.setter
    @abstractmethod
    def creation_datetime(self, value: int) -> None:
        pass

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

class TXTransactionBase(ABC):
    _uuid: str
    _oder: int
    def __init__(self, uuid: str = None):
        self._uuid = str(u.uuid4()) if uuid is None else uuid
        self.order = 0
    @property
    def order(self) -> int:
        return self._order
    @order.setter
    def order(self, value: int) -> None:
        self._order = value
    @property
    @abstractmethod
    def origin_order(self) -> 'TXTransactionBase':
        pass
    @origin_order.setter
    @abstractmethod
    def origin_order(self, value: 'TXTransactionBase') -> None:
        pass
    @property
    @abstractmethod
    def source_wallet(self) -> TXWalletBase:
        pass
    @source_wallet.setter
    @abstractmethod
    def source_wallet(self, value: TXWalletBase) -> None:
        pass
    @property
    @abstractmethod
    def target_wallet(self) -> TXWalletBase:
        pass
    @target_wallet.setter
    @abstractmethod
    def target_wallet(self, value: TXWalletBase) -> None:
        pass
    @property
    @abstractmethod
    def bot(self) -> TXBotBase:
        pass
    @bot.setter
    @abstractmethod
    def bot(self, value: TXBotBase) -> None:
        pass
    @property
    @abstractmethod
    def start_datetime(self) -> int:
        pass
    @start_datetime.setter
    @abstractmethod
    def start_datetime(self, value: int) -> None:
        pass
    @property
    @abstractmethod
    def end_datetime(self) -> int:
        pass
    @end_datetime.setter
    @abstractmethod
    def end_datetime(self, value: int) -> None:
        pass
    @property
    def operational_mode(self) -> TXTransOperationalMode:
        pass
    @operational_mode.setter
    @abstractmethod
    def operational_mode(self, value: TXTransOperationalMode) -> None:
        pass
    @property
    @abstractmethod
    def source_value(self) -> float:
        pass
    @source_value.setter
    @abstractmethod
    def source_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        pass
    @property
    @abstractmethod
    def target_value(self) -> float:
        pass
    @target_value.setter
    @abstractmethod
    def target_value(self, value: float) -> None:
        TXUtils.validate_float_precision(value, 25, 10)
        pass
    @property
    @abstractmethod
    def status(self) -> TXTransStatus:
        pass
    @status.setter
    @abstractmethod
    def status(self, value: TXTransStatus) -> None:
        pass
    @property
    @abstractmethod
    def annotations(self) -> str:
        pass
    @annotations.setter
    @abstractmethod
    def annotations(self, value: str) -> None:
        pass

