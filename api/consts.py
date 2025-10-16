from trivorxlib.storages.mysql import TXMySQLStorage
from trivorxlib.core.base import TXUtils

TX_STORAGE = TXMySQLStorage(TXUtils.read_text_file("mysql_settings.json"))
