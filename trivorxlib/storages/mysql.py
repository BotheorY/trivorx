from trivorxlib.core.base import *
from trivorxlib.storages.base import *
from typing import Any, Dict, Tuple, Optional
from mysql.connector import Error as MySQLError
from mysql.connector import pooling
import warnings
import pathlib
import json
from datetime import datetime as dt
import threading
from contextlib import contextmanager

class TXSQLBuilder:
    """SQL generator for TXQueryNode trees supporting CRUD operations (MySQL dialect).

    This class provides static methods to generate parameterized SQL queries from TXQueryNode trees, supporting SELECT, INSERT, UPDATE, and DELETE operations with MySQL-specific syntax.
    All methods return SQL strings with parameter lists for use with parameterized queries to prevent SQL injection attacks.

    Attributes:
        placeholder (str): MySQL-style parameter placeholder ("%s").
    """

    placeholder: str = "%s"  # MySQL-style placeholder

    @staticmethod
    def select(
        table: str,
        columns: Optional[list[str]] = None,
        where: Optional[TXQueryNode] = None,
        order_by: Optional[list[TXSortCriterion]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Generate a SELECT SQL statement with optional filtering, ordering, and pagination.

        Args:
            table (str): The name of the table to select from.
            columns (Optional[list[str]]): List of column names to select. If None, selects all columns (*).
            where (Optional[TXQueryNode]): Query conditions tree for filtering results.
            order_by (Optional[list[TXSortCriterion]]): List of sort criteria for ordering results.
            limit (Optional[int]): Maximum number of rows to return.
            offset (Optional[int]): Number of rows to skip before returning results.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types for proper parameter handling.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL query string and list of parameters.

        Example:
            >>> sql, params = TXSQLBuilder.select("users", ["id", "name"], 
            ...                                   TXCondition(TXStorageQueryOps.EQUALS, "active", True))
            >>> print(sql)
            SELECT id, name FROM `users` WHERE `active` = %s
        """
        cols = ", ".join(columns) if columns else "*"
        where_sql, params = TXSQLBuilder._build_where(where, field_types)
        sql = f"SELECT {cols} FROM `{table}`"
        if where_sql:
            sql += f" {where_sql}"
        if order_by:
            sort_parts = [f"`{crit.field}` {crit.direction.value}" for crit in order_by]
            sql += f" ORDER BY {', '.join(sort_parts)}"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"
        return sql, params

    @staticmethod
    def insert(
        table: str,
        data: Dict[str, Any],
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Generate an INSERT SQL statement for inserting a single row.

        Args:
            table (str): The name of the table to insert into.
            data (Dict[str, Any]): Dictionary mapping column names to values to insert.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types for proper parameter handling.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL query string and list of parameters.

        Raises:
            ValueError: If the data dictionary is empty.

        Example:
            >>> sql, params = TXSQLBuilder.insert("users", {"name": "John", "age": 30})
            >>> print(sql)
            INSERT INTO `users` (`name`, `age`) VALUES (%s, %s)
        """
        if not data:
            raise ValueError("Insert data cannot be empty")
        cols = ", ".join(f"`{c}`" for c in data.keys())
        placeholders = ", ".join(TXSQLBuilder.placeholder for _ in data)
        values = [TXSQLBuilder._param_value(k, v, field_types) for k, v in data.items()]
        sql = f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders})"
        return sql, values

    @staticmethod
    def update(
        table: str,
        data: Dict[str, Any],
        where: Optional[TXQueryNode] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Generate an UPDATE SQL statement for modifying existing rows.

        Args:
            table (str): The name of the table to update.
            data (Dict[str, Any]): Dictionary mapping column names to new values.
            where (Optional[TXQueryNode]): Query conditions tree for filtering rows to update. If None, all rows will be updated.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types for proper parameter handling.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL query string and list of parameters.

        Raises:
            ValueError: If the data dictionary is empty.

        Example:
            >>> sql, params = TXSQLBuilder.update("users", {"age": 31}, 
            ...                                   TXCondition(TXStorageQueryOps.EQUALS, "id", 1))
            >>> print(sql)
            UPDATE `users` SET `age` = %s WHERE `id` = %s
        """
        if not data:
            raise ValueError("Update data cannot be empty")
        set_parts: list[str] = []
        params: list[Any] = []
        for k, v in data.items():
            set_parts.append(f"`{k}` = {TXSQLBuilder.placeholder}")
            params.append(TXSQLBuilder._param_value(k, v, field_types))
        where_sql, where_params = TXSQLBuilder._build_where(where, field_types)
        sql = f"UPDATE `{table}` SET {', '.join(set_parts)}"
        if where_sql:
            sql += f" {where_sql}"
            params.extend(where_params)
        return sql, params

    @staticmethod
    def delete(
        table: str,
        where: Optional[TXQueryNode] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Generate a DELETE SQL statement for removing rows.

        Args:
            table (str): The name of the table to delete from.
            where (Optional[TXQueryNode]): Query conditions tree for filtering rows to delete. If None, all rows will be deleted.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types for proper parameter handling.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL query string and list of parameters.

        Warning:
            Be extremely careful when using this method without a WHERE clause, as it will
            delete all rows from the table.

        Example:
            >>> sql, params = TXSQLBuilder.delete("users", 
            ...                                   TXCondition(TXStorageQueryOps.EQUALS, "active", False))
            >>> print(sql)
            DELETE FROM `users` WHERE `active` = %s
        """
        where_sql, params = TXSQLBuilder._build_where(where, field_types)
        sql = f"DELETE FROM `{table}`"
        if where_sql:
            sql += f" {where_sql}"
        return sql, params

    # --- Internal helpers ---
    @staticmethod
    def _build_where(
        node: Optional[TXQueryNode],
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Build WHERE clause from a TXQueryNode tree.

        Args:
            node (Optional[TXQueryNode]): The query node tree to convert to SQL.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the WHERE clause string and parameters.
                                  Returns empty string and empty list if node is None.
        """
        if node is None:
            return "", []
        clause, params = TXSQLBuilder._node_to_sql(node, field_types)
        return f"WHERE {clause}", params

    @staticmethod
    def _node_to_sql(
        node: TXQueryNode,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        """Convert a TXQueryNode to SQL clause and parameters.

        Args:
            node (TXQueryNode): The query node to convert (TXCondition, TXUnaryQuery, or TXLogicalQuery).
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL clause string and parameters.

        Raises:
            ValueError: If the node type is not supported.
        """
        if isinstance(node, TXCondition):
            return TXSQLBuilder._condition_sql(node, field_types)
        if isinstance(node, TXUnaryQuery):
            inner_sql, inner_params = TXSQLBuilder._node_to_sql(node.operand, field_types)
            return f"NOT ({inner_sql})", inner_params
        if isinstance(node, TXLogicalQuery):
            left_sql, left_params = TXSQLBuilder._node_to_sql(node.left, field_types)
            right_sql, right_params = TXSQLBuilder._node_to_sql(node.right, field_types)
            op = "AND" if node.operator == TXStorageQueryOps.AND else "OR"
            return f"({left_sql}) {op} ({right_sql})", left_params + right_params
        raise ValueError("Unsupported TXQueryNode subclass")

    @staticmethod
    def _condition_sql(cond: TXCondition, field_types: Optional[Dict[str, str]]) -> Tuple[str, list[Any]]:
        """Convert a TXCondition to SQL clause and parameters.

        Handles various comparison operators including NULL semantics, LIKE patterns, and JSON operations for MySQL.

        Args:
            cond (TXCondition): The condition to convert to SQL.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types.

        Returns:
            Tuple[str, list[Any]]: A tuple containing the SQL condition string and parameters.

        Raises:
            ValueError: If the operator is not supported.

        Note:
            - NULL values are handled with IS NULL/IS NOT NULL syntax
            - JSON operations use MySQL's JSON_CONTAINS function
            - LIKE operations are properly escaped for pattern matching
        """
        col = f"`{cond.field}`"
        op = cond.operator
        val = cond.value

        # Handle NULL semantics
        if val is None:
            if op == TXStorageQueryOps.EQUALS:
                return f"{col} IS NULL", []
            if op == TXStorageQueryOps.NOT_EQUALS:
                return f"{col} IS NOT NULL", []

        if op == TXStorageQueryOps.EQUALS:
            return f"{col} = {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.NOT_EQUALS:
            return f"{col} <> {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.GREATER_THAN:
            return f"{col} > {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.LESS_THAN:
            return f"{col} < {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.STARTS_WITH:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_prefix(val)]
        if op == TXStorageQueryOps.ENDS_WITH:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_suffix(val)]
        if op == TXStorageQueryOps.CONTAINS:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_contains(val)]
        if op == TXStorageQueryOps.INCLUDES_VALUES:
            # MySQL JSON: ensure column contains all specified values
            # JSON_CONTAINS(col, CAST(? AS JSON))
            candidate = json.dumps(val)
            return (
                f"JSON_CONTAINS({col}, CAST({TXSQLBuilder.placeholder} AS JSON))",
                [candidate],
            )
        if op == TXStorageQueryOps.NOT_INCLUDES_VALUES:
            candidate = json.dumps(val)
            return (
                f"NOT JSON_CONTAINS({col}, CAST({TXSQLBuilder.placeholder} AS JSON))",
                [candidate],
            )
        raise ValueError(f"Unsupported operator: {op}")

    @staticmethod
    def _param_value(field: str, value: Any, field_types: Optional[Dict[str, str]]) -> Any:
        """Convert a Python value to appropriate database parameter value.

        Args:
            field (str): The field name for type lookup.
            value (Any): The Python value to convert.
            field_types (Optional[Dict[str, str]]): Mapping of field names to their data types.

        Returns:
            Any: The converted value suitable for database parameter binding.

        Note:
            - Boolean values are converted to 1/0 for MySQL compatibility
            - JSON field types are serialized to JSON strings
            - Other values are returned as-is
        """
        t = (field_types or {}).get(field)
        if isinstance(value, bool):
            return 1 if value else 0
        if t == "json":
            return json.dumps(value)
        return value

    @staticmethod
    def _like_prefix(value: Any) -> str:
        """Create a LIKE pattern for prefix matching (value%).

        Args:
            value (Any): The value to create a prefix pattern for.

        Returns:
            str: A LIKE pattern string for prefix matching.
        """
        s = str(value)
        return f"{s}%"

    @staticmethod
    def _like_suffix(value: Any) -> str:
        """Create a LIKE pattern for suffix matching (%value).

        Args:
            value (Any): The value to create a suffix pattern for.

        Returns:
            str: A LIKE pattern string for suffix matching.
        """
        s = str(value)
        return f"%{s}"

    @staticmethod
    def _like_contains(value: Any) -> str:
        """Create a LIKE pattern for substring matching (%value%).

        Args:
            value (Any): The value to create a contains pattern for.

        Returns:
            str: A LIKE pattern string for substring matching.
        """
        s = str(value)
        return f"%{s}%"

class TXMySQLStorage(TXStorageBase):
    """MySQL storage implementation for the TrivorX trading system.

    This class provides a complete MySQL-based storage backend implementing all CRUD operations for users, bots, currencies, exchange data sources, financial hubs, wallets, and transactions.
    It uses connection pooling for optimal performance and supports advanced query operations through the TXQueryNode system.

    Features:
        - Connection pooling with automatic reconnection
        - Thread-safe operations with proper locking
        - Parameterized queries to prevent SQL injection
        - Soft deletion for most entities
        - JSON field support for flexible data storage
        - Comprehensive error handling and logging

    Attributes:
        _pool (pooling.MySQLConnectionPool): The MySQL connection pool instance.
        _pool_lock (threading.Lock): Thread lock for pool operations.
        DEFAULT_POOL_SIZE (int): Default number of connections in the pool (10).
        DEFAULT_MAX_OVERFLOW (int): Default maximum overflow connections (20).
        DEFAULT_POOL_RESET_SESSION (bool): Whether to reset sessions (True).
        DEFAULT_POOL_PRE_PING (bool): Whether to pre-ping connections (True).
        DEFAULT_POOL_RECYCLE (int): Connection recycle time in seconds (3600).
        DEFAULT_POOL_TIMEOUT (int): Pool timeout in seconds (30).
    """
    _pool: pooling.MySQLConnectionPool = None
    _pool_lock = threading.Lock()
    
    # Connection pool configuration constants
    DEFAULT_POOL_SIZE = 10
    DEFAULT_MAX_OVERFLOW = 20
    DEFAULT_POOL_RESET_SESSION = True
    DEFAULT_POOL_PRE_PING = True
    DEFAULT_POOL_RECYCLE = 3600  # 1 hour
    DEFAULT_POOL_TIMEOUT = 30

    def __init__(self, settings_json: str):
        """Initialize the MySQL storage with connection settings.

        Args:
            settings_json (str): JSON string containing MySQL connection parameters.
            Required keys: host, user, password, database.
            Optional keys: port, charset, collation, connect_timeout, read_timeout, write_timeout, pool_size, max_overflow, pool_timeout, pool_recycle.

        Raises:
            ValueError: If required connection parameters are missing.
            TypeError: If connection parameters have incorrect types.
            RuntimeError: If connection pool initialization fails.
        """
        super().__init__(settings_json)
        self._create_tables()

    @property
    @settings_json.setter
    def settings_json(self, value: str) -> None:
        """Set and validate MySQL connection settings.

        Validates all connection parameters and reinitializes the connection pool with the new settings. Performs comprehensive type checking for all supported MySQL connection parameters.

        Args:
            value (str): JSON string containing MySQL connection settings.

        Raises:
            ValueError: If required connection parameters are missing.
            TypeError: If any connection parameter has an incorrect type.
            RuntimeError: If connection pool reinitialization fails.

        Required Parameters:
            - host (str): MySQL server hostname or IP address
            - user (str): MySQL username
            - password (str): MySQL password
            - database (str): MySQL database name

        Optional Parameters:
            - port (int): MySQL server port (default: 3306)
            - charset (str): Character set (default: utf8mb4)
            - collation (str): Collation (default: utf8mb4_general_ci)
            - connect_timeout (int): Connection timeout in seconds
            - read_timeout (int): Read timeout in seconds
            - write_timeout (int): Write timeout in seconds
            - pool_size (int): Number of connections in pool
            - max_overflow (int): Maximum overflow connections
            - pool_timeout (int): Pool timeout in seconds
            - pool_recycle (int): Connection recycle time in seconds
        """
        super().settings_json = value
        required_keys = {"host", "user", "password", "database"}
        missing = required_keys - self._settings.keys()
        if missing:
            raise ValueError(f"Missing required MySQL connection parameters: {', '.join(sorted(missing))}")
        if not isinstance(self._settings["host"], str):
            raise TypeError("The 'host' parameter must be a string.")
        if not isinstance(self._settings["user"], str):
            raise TypeError("The 'user' parameter must be a string.")
        if not isinstance(self._settings["password"], str):
            raise TypeError("The 'password' parameter must be a string.")
        if not isinstance(self._settings["database"], str):
            raise TypeError("The 'database' parameter must be a string.")
        if "port" in self._settings and not isinstance(self._settings["port"], int):
            raise TypeError("The 'port' parameter must be an integer.")
        if "charset" in self._settings and not isinstance(self._settings["charset"], str):
            raise TypeError("The 'charset' parameter must be a string.")
        if "collation" in self._settings and not isinstance(self._settings["collation"], str):
            raise TypeError("The 'collation' parameter must be a string.")
        if "connect_timeout" in self._settings and not isinstance(self._settings["connect_timeout"], int):
            raise TypeError("The 'connect_timeout' parameter must be an integer.")
        if "read_timeout" in self._settings and not isinstance(self._settings["read_timeout"], int):
            raise TypeError("The 'read_timeout' parameter must be an integer.")
        if "write_timeout" in self._settings and not isinstance(self._settings["write_timeout"], int):
            raise TypeError("The 'write_timeout' parameter must be an integer.")
        
        # Validate pool-specific settings
        if "pool_size" in self._settings and not isinstance(self._settings["pool_size"], int):
            raise TypeError("The 'pool_size' parameter must be an integer.")
        if "max_overflow" in self._settings and not isinstance(self._settings["max_overflow"], int):
            raise TypeError("The 'max_overflow' parameter must be an integer.")
        if "pool_timeout" in self._settings and not isinstance(self._settings["pool_timeout"], int):
            raise TypeError("The 'pool_timeout' parameter must be an integer.")
        if "pool_recycle" in self._settings and not isinstance(self._settings["pool_recycle"], int):
            raise TypeError("The 'pool_recycle' parameter must be an integer.")
            
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the MySQL connection pool with optimal configuration.

        Creates a new MySQL connection pool using the current settings, properly closing any existing pool connections first. Uses thread-safe operations and comprehensive error handling.

        Raises:
            RuntimeError: If MySQL connection pool initialization fails.

        Note:
            This method is automatically called when settings are updated and should not be called directly under normal circumstances.
        """
        with self._pool_lock:
            if self._pool is not None:
                try:
                    # Close existing pool connections
                    for _ in range(self._pool.pool_size):
                        try:
                            conn = self._pool.get_connection()
                            if conn.is_connected():
                                conn.close()
                        except:
                            pass
                except:
                    pass
            
            pool_config = {
                'pool_name': f'trivorx_pool_{id(self)}',
                'pool_size': self._settings.get("pool_size", self.DEFAULT_POOL_SIZE),
                'pool_reset_session': self._settings.get("pool_reset_session", self.DEFAULT_POOL_RESET_SESSION),
                'host': self._settings["host"],
                'user': self._settings["user"],
                'password': self._settings["password"],
                'database': self._settings["database"],
                'port': self._settings.get("port", 3306),
                'charset': self._settings.get("charset", "utf8mb4"),
                'collation': self._settings.get("collation", "utf8mb4_general_ci"),
                'connect_timeout': self._settings.get("connect_timeout", 10),
                'autocommit': False,
                'use_unicode': True,
                'raise_on_warnings': True,
            }
            
            try:
                self._pool = pooling.MySQLConnectionPool(**pool_config)
            except MySQLError as exc:
                raise RuntimeError(f"MySQL connection pool initialization failed: {exc}") from exc
            except Exception as exc:
                raise RuntimeError(f"Unexpected error while initializing MySQL connection pool: {exc}") from exc

    @contextmanager
    def _get_connection(self):
        """Context manager to get a connection from the pool and ensure it's returned.

        Provides a safe way to obtain and use MySQL connections from the pool.
        Automatically handles connection validation, session configuration, error handling, and proper connection cleanup.

        Yields:
            mysql.connector.MySQLConnection: A validated MySQL connection from the pool.

        Raises:
            RuntimeError: If connection pool errors or MySQL connection errors occur.

        Features:
            - Automatic connection health validation with reconnection
            - Session-specific timeout configuration
            - Automatic rollback on errors
            - Guaranteed connection return to pool
            - Comprehensive error handling and logging

        Example:
            >>> with self._get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM users")
            ...     results = cursor.fetchall()
        """
        if self._pool is None:
            self._initialize_pool()
        
        connection = None
        try:
            # Get connection from pool with timeout
            pool_timeout = self._settings.get("pool_timeout", self.DEFAULT_POOL_TIMEOUT)
            connection = self._pool.get_connection(timeout=pool_timeout)
            
            # Validate connection health
            if not connection.is_connected():
                connection.reconnect(attempts=3, delay=1)
            
            # Set session-specific timeouts if configured
            if "read_timeout" in self._settings or "write_timeout" in self._settings:
                cursor = connection.cursor()
                try:
                    if "read_timeout" in self._settings:
                        cursor.execute("SET SESSION net_read_timeout = %s", (self._settings['read_timeout'],))
                    if "write_timeout" in self._settings:
                        cursor.execute("SET SESSION net_write_timeout = %s", (self._settings['write_timeout'],))
                finally:
                    cursor.close()
            
            yield connection
            
        except pooling.PoolError as exc:
            raise RuntimeError(f"Connection pool error: {exc}") from exc
        except MySQLError as exc:
            if connection:
                try:
                    connection.rollback()
                except:
                    pass
            raise RuntimeError(f"MySQL connection error: {exc}") from exc
        finally:
            if connection:
                try:
                    # Return connection to pool
                    connection.close()
                except Exception as exc:
                    warnings.warn(f"Error returning connection to pool: {exc}", RuntimeWarning)

    def close(self) -> None:
        """Safely close all connections in the pool.

        Gracefully shuts down the MySQL connection pool by closing all active connections. This method should be called when the storage instance is no longer needed to free up database resources.

        Note:
            This method is thread-safe and can be called multiple times safely.
            After calling this method, the connection pool will be reinitialized automatically on the next database operation.
        """
        with self._pool_lock:
            if self._pool is not None:
                try:
                    # Close all connections in the pool
                    for _ in range(self._pool.pool_size):
                        try:
                            conn = self._pool.get_connection(timeout=1)
                            if conn.is_connected():
                                conn.close()
                        except:
                            pass
                except Exception as exc:
                    warnings.warn(f"Error while closing connection pool: {exc}", RuntimeWarning)
                finally:
                    self._pool = None

    def __enter__(self):
        """Context manager entry point.

        Returns:
            TXMySQLStorage: The storage instance for use in with statements.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point.

        Automatically closes the connection pool when exiting the context.

        Args:
            exc_type: Exception type (if any).
            exc_val: Exception value (if any).
            exc_tb: Exception traceback (if any).
        """
        self.close()

    def _ensure_connection(self) -> None:
        """Ensure the connection pool is initialized.

        Checks if the connection pool exists and initializes it if necessary.
        This is a utility method used internally to guarantee pool availability.

        Note:
            This method is called automatically by database operations and
            should not be called directly under normal circumstances.
        """
        if self._pool is None:
            self._initialize_pool()

    def _create_tables(self) -> None:
        """Create all tables by executing the statements contained in db_mysql.sql.

        Reads and executes the SQL schema file to create all necessary database tables and structures. Also creates the default administrator user if it doesn't already exist.

        Raises:
            FileNotFoundError: If the db_mysql.sql schema file is not found.
            RuntimeError: If table creation or default user creation fails.

        Note:
            This method is called automatically during initialization and
            should not be called directly under normal circumstances.
        """
        sql_file = pathlib.Path(__file__).with_name("db_mysql.sql")
        if not sql_file.exists():
            raise FileNotFoundError(f"Schema file not found: {sql_file}")

        with sql_file.open("r", encoding="utf-8") as f:
            raw = f.read()

        # Split on semicolon, strip blanks, drop empty statements
        statements = [stmt.strip() for stmt in raw.split(";") if stmt.strip()]
        
        with self._get_connection() as connection:
            cursor = connection.cursor()
            try:
                for stmt in statements:
                    cursor.execute(stmt)                
                connection.commit()
                
                # [START] CHECK IF THE PRIMARY ADMINISTRATOR USER EXISTS AND CREATE IT IF NOT
                sql, params = TXSQLBuilder.select(
                    table="user",
                    columns=[
                        "user_uuid",
                        "login"
                    ],
                    where=TXCondition(TXStorageQueryOps.EQUALS, "login", "admin")
                )
                try:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    cursor.close()
                except MySQLError as exc:
                    raise RuntimeError(f"Failed to fetch primary administrator user: {exc}") from exc
                if not rows:
                    sql, params = TXSQLBuilder.insert(
                        table="user",
                        data={
                            "full_name": "Administrator",
                            "login": "admin",
                            "password": TXUtils.encrypt_password("admin"),
                            "token": TXUtils.generate_token(),
                            "role": TXUserRole.ADMIN.value
                        }
                    )
                    try:
                        cursor = connection.cursor()
                        cursor.execute(sql, params)
                        connection.commit()
                    except MySQLError as exc:
                        connection.rollback()
                        raise RuntimeError(f"Failed to create primary administrator user: {exc}") from exc
                # [END] CHECK IF THE PRIMARY ADMINISTRATOR USER EXISTS AND CREATE IT IF NOT
            except MySQLError as exc:
                connection.rollback()
                raise RuntimeError(f"Table creation failed: {exc}") from exc
            finally:
                cursor.close()

    # --- Internal: query field translation helpers ---
    def _translate_query_fields(self, node: Optional[TXQueryNode], mapping: Dict[str, str]) -> Optional[TXQueryNode]:
        """Recursively translate condition fields using provided mapping.

        Traverses a TXQueryNode tree and replaces field names according to the provided mapping dictionary. This is useful for translating between different field naming conventions or database schemas.

        Args:
            node (Optional[TXQueryNode]): The query node tree to translate.
            mapping (Dict[str, str]): Dictionary mapping old field names to new field names.

        Returns:
            Optional[TXQueryNode]: A new query node tree with translated field names or None if the input node was None.

        Note:
            This method creates a new query tree and does not modify the original.
            Fields not found in the mapping dictionary are left unchanged.
        """
        if node is None:
            return None
        if isinstance(node, TXCondition):
            new_field = mapping.get(node.field, node.field)
            return TXCondition(node.operator, new_field, node.value)
        if isinstance(node, TXUnaryQuery):
            return TXUnaryQuery(node.operator, self._translate_query_fields(node.operand, mapping))
        if isinstance(node, TXLogicalQuery):
            left = self._translate_query_fields(node.left, mapping)
            right = self._translate_query_fields(node.right, mapping)
            return TXLogicalQuery(node.operator, left, right)
        return node

    def get_users(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXUserBase]:
        """Retrieve users matching the given query, sort, offset, and limit.

        Fetches user records from the database with optional filtering, sorting and pagination. Only returns non-deleted users (soft deletion support).

        Args:
            query (Optional[TXQueryNode]): Query conditions for filtering users. If None, returns all non-deleted users.
            sort (Optional[list[TXSortCriterion]]): List of sort criteria for ordering results.
            offset (Optional[int]): Number of records to skip (for pagination).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            list[TXUserBase]: List of TXUserBase objects matching the criteria.

        Raises:
            RuntimeError: If the database query fails.

        Example:
            >>> # Get all active admin users
            >>> admin_query = TXCondition(TXStorageQueryOps.EQUALS, "role", "ADMIN")
            >>> users = storage.get_users(query=admin_query, limit=10)
        """
        sql, params = TXSQLBuilder.select(
            table="user",
            columns=[
                "user_uuid",
                "full_name",
                "login",
                "password",
                "token",
                "role",
                "2fa_seed",
                "enabled",
                "UNIX_TIMESTAMP(creation_datetime) AS creation_ts"
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to fetch users: {exc}") from exc
                
        users: list[TXUserBase] = []
        for row in rows:
            user = TXUserBase(
                uuid=row["user_uuid"],
                token=row["token"],
                encrypted_password=row["password"],
            )
            if row["role"] == "ADMIN":
                user.role = TXUserRole.ADMIN
            else:
                user.role = TXUserRole.STANDARD
            user.full_name = row["full_name"]
            user.login = row["login"]
            user.twofa_seed = row.get("2fa_seed")
            user.enabled = bool(row["enabled"])
            user.creation_datetime = int(row["creation_ts"])            
            users.append(user)
        return users

    def update_user(
        self,
        uuid: str, 
        token: Optional[str] = None,
        full_name: Optional[str] = None,
        login: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[TXUserRole] = None,
        enabled: Optional[bool] = None,
        encrypted_password: Optional[str] = None,
        twofa_seed: Optional[str] = None
    ) -> None:
        """Update an existing user in the storage.

        Updates user information in the database. Only provided parameters will be updated; None values are ignored. Passwords can be provided either as plain text (password) or pre-encrypted (encrypted_password).

        Args:
            uuid (str): The UUID of the user to update.
            token (Optional[str]): New authentication token.
            full_name (Optional[str]): New full name.
            login (Optional[str]): New login username.
            password (Optional[str]): New plain text password (will be encrypted).
            role (Optional[TXUserRole]): New user role (ADMIN or STANDARD).
            enabled (Optional[bool]): Whether the user account is enabled.
            encrypted_password (Optional[str]): Pre-encrypted password (takes precedence over password).
            twofa_seed (Optional[str]): Two-factor authentication seed.

        Raises:
            RuntimeError: If the database update fails.

        Note:
            If both password and encrypted_password are provided, encrypted_password takes precedence and password is ignored.
        """
        data: Dict[str, Any] = {}
        if token is not None:
            data["token"] = token
        if full_name is not None:
            data["full_name"] = full_name
        if login is not None:
            data["login"] = login
        if password and encrypted_password is None:
            data["password"] = TXUtils.encrypt_password(password)
        elif encrypted_password is not None:
            data["password"] = encrypted_password
        if role is not None:
            data["role"] = role.value
        if enabled is not None:
            data["enabled"] = int(enabled)
        # Always synchronize 2FA seed; allow NULL when value is None
        data["2fa_seed"] = twofa_seed
        sql, params = TXSQLBuilder.update(
            table="user",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", uuid),
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to update user: {exc}") from exc

    def delete_user(self, uuid: str) -> None:
        """Delete a user from the storage (soft delete).

        Marks a user as deleted by setting the deleted flag to 1. The user
        record remains in the database but will be excluded from normal queries.

        Args:
            uuid (str): The UUID of the user to delete.

        Raises:
            RuntimeError: If the database update fails.

        Note:
            This is a soft delete operation. The user record is not physically removed from the database but marked as deleted.
        """
        sql, params = TXSQLBuilder.update(
            table="user",
            data={
                "deleted": 1
            },
            where=TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", uuid)
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to delete user: {exc}") from exc

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
        """Insert a new user into the storage.

        Creates a new user record in the database with the provided information.
        Automatically generates UUID and token if not provided. Handles password encryption if plain text password is provided.

        Args:
            full_name (str): The user's full name.
            login (str): The user's login username (must be unique).
            role (TXUserRole): The user's role (ADMIN or STANDARD).
            password (Optional[str]): Plain text password (will be encrypted).
            encrypted_password (Optional[str]): Pre-encrypted password (takes precedence over password).
            uuid (Optional[str]): User UUID (auto-generated if None).
            token (Optional[str]): Authentication token (auto-generated if None).
            twofa_seed (Optional[str]): Two-factor authentication seed.

        Returns:
            tuple[str, str]: A tuple containing (user_uuid, token).

        Raises:
            ValueError: If neither password nor encrypted_password is provided.
            RuntimeError: If the database insert fails.

        Note:
            If both password and encrypted_password are provided, encrypted_password takes precedence and password is ignored.
        """
        uuid = TXUtils.generate_uuid() if uuid is None else uuid
        token = TXUtils.generate_token() if token is None else token
        if password is not None and encrypted_password is None:
            encrypted_password = TXUtils.encrypt_password(password)
        elif encrypted_password is None:
            raise ValueError("Either password or encrypted_password must be provided.")
        sql, params = TXSQLBuilder.insert(
            table="user",
            data={
                "user_uuid": uuid,
                "full_name": full_name,
                "login": login,
                "password": encrypted_password,
                "token": token,
                "role": role.value,
                "2fa_seed": twofa_seed,
            },
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to insert user: {exc}") from exc
        return uuid, token

    # --- BOT CRUD ---
    def get_bots(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXBotBase]:
        """Retrieve bots matching the given query, sort, offset, and limit.

        Fetches bot records from the database with optional filtering, sorting and pagination. Only returns non-deleted bots (soft deletion support).
        Each bot includes its associated user and algorithm information.

        Args:
            query (Optional[TXQueryNode]): Query conditions for filtering bots. If None, returns all non-deleted bots.
            sort (Optional[list[TXSortCriterion]]): List of sort criteria for ordering results.
            offset (Optional[int]): Number of records to skip (for pagination).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            list[TXBotBase]: List of TXBotBase objects matching the criteria.

        Raises:
            RuntimeError: If the database query fails.

        Note:
            This method automatically fetches and includes the associated user information for each bot.
        """
        sql, params = TXSQLBuilder.select(
            table="bot",
            columns=[
                "bot_uuid",
                "user_uuid",
                "algo_uuid",
                "name",
                "algo_name",
                "algo_version",
                "algo_settings",
                "annotations",
                "active",
                "UNIX_TIMESTAMP(creation_datetime) AS creation_ts",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to fetch bots: {exc}") from exc
                
        bots: list[TXBotBase] = []
        for row in rows:
            user = self.get_users(TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"]))[0]
            bot = TXBotBase(
                user=user,
                algo_uuid=row["algo_uuid"],
                name=row["name"],
                algo_name = row["algo_name"],
                algo_ver=row["algo_version"],
                algo_settings=row["algo_settings"],
                uuid=row["bot_uuid"],
            )
            bot.annotations = row.get("annotations")
            bot.active = bool(row["active"])
            bot.creation_datetime = int(row["creation_ts"])
            bots.append(bot)
        return bots

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
        """Insert a new bot into the storage and return its UUID.

        Creates a new bot record in the database with the provided information.
        Automatically generates a UUID if not provided.

        Args:
            user_uuid (str): The UUID of the user who owns this bot.
            algo_uuid (str): The UUID of the algorithm this bot uses.
            name (str): The display name for the bot.
            algo_name (str): The name of the algorithm.
            algo_ver (str): The version of the algorithm.
            algo_settings (str): JSON string containing algorithm-specific settings.
            annotations (Optional[str]): Optional additional notes or metadata about the bot.
            active (Optional[bool]): Whether the bot is active. Defaults to False if None.
            uuid (Optional[str]): Bot UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created bot.

        Raises:
            RuntimeError: If the database insert operation fails.

        Example:
            >>> bot_uuid = storage.insert_bot(
            ...     user_uuid="user-123",
            ...     algo_uuid="algo-456",
            ...     name="My Trading Bot",
            ...     algo_name="RSI Strategy",
            ...     algo_ver="1.0.0",
            ...     algo_settings='{"rsi_period": 14}'
            ... )
        """
        bot_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "bot_uuid": bot_uuid,
            "user_uuid": user_uuid,
            "algo_uuid": algo_uuid,
            "name": name,
            "algo_name": algo_name,
            "algo_version": algo_ver,
            "algo_settings": algo_settings,
            "annotations": annotations,
            "active": int(active) if active is not None else 0,
        }
        sql, params = TXSQLBuilder.insert(
            table="bot",
            data=data,
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to insert bot: {exc}") from exc
        return bot_uuid

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
        active: Optional[bool] = None
    ) -> None:
        """Update an existing bot in the storage.

        Updates bot information in the database. Only provided parameters will be updated;
        None values are ignored, allowing for partial updates.

        Args:
            uuid (str): The UUID of the bot to update.
            user_uuid (Optional[str]): New owner user UUID.
            algo_uuid (Optional[str]): New algorithm UUID.
            name (Optional[str]): New display name for the bot.
            algo_name (Optional[str]): New algorithm name.
            algo_ver (Optional[str]): New algorithm version.
            algo_settings (Optional[str]): New JSON string containing algorithm settings.
            annotations (Optional[str]): New additional notes or metadata.
            active (Optional[bool]): New active status for the bot.

        Raises:
            RuntimeError: If the database update operation fails.

        Example:
            >>> storage.update_bot(
            ...     uuid="bot-123",
            ...     name="Updated Bot Name",
            ...     active=True
            ... )
        """
        data: Dict[str, Any] = {}
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if algo_uuid is not None:
            data["algo_uuid"] = algo_uuid
        if name is not None:
            data["name"] = name
        if algo_name is not None:
            data["algo_name"] = algo_name
        if algo_ver is not None:
            data["algo_version"] = algo_ver
        if algo_settings is not None:
            data["algo_settings"] = algo_settings
        if annotations is not None:
            data["annotations"] = annotations
        if active is not None:
            data["active"] = int(active)
        sql, params = TXSQLBuilder.update(
            table="bot",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", uuid),
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to update bot: {exc}") from exc

    def delete_bot(self, uuid: str) -> None:
        """Delete a bot from the storage (soft delete).

        Marks a bot as deleted by setting the deleted flag to 1. The bot record remains in the database but will be excluded from normal queries.

        Args:
            uuid (str): The UUID of the bot to delete.

        Raises:
            RuntimeError: If the database update operation fails.

        Note:
            This is a soft delete operation. The bot record is not physically removed from the database but marked as deleted.

        Example:
            >>> storage.delete_bot("bot-123")
        """
        sql, params = TXSQLBuilder.update(
            table="bot",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", uuid),
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to delete bot: {exc}") from exc

    # --- CURRENCY CRUD ---
    def get_currencies(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXCurrencyBase]:
        """Retrieve currencies matching the given query, sort, offset, and limit.

        Fetches currency records from the database with optional filtering, sorting and pagination.
        Only returns non-deleted currencies (soft deletion support).

        Args:
            query (Optional[TXQueryNode]): Query conditions for filtering currencies. If None, returns all non-deleted currencies.
            sort (Optional[list[TXSortCriterion]]): List of sort criteria for ordering results.
            offset (Optional[int]): Number of records to skip (for pagination).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            list[TXCurrencyBase]: List of TXCurrencyBase objects matching the criteria.

        Raises:
            RuntimeError: If the database query fails.

        Example:
            >>> # Get all cryptocurrencies
            >>> crypto_query = TXCondition(TXStorageQueryOps.EQUALS, "currency_type", "CRYPTO")
            >>> currencies = storage.get_currencies(query=crypto_query, limit=10)
        """
        sql, params = TXSQLBuilder.select(
            table="currency",
            columns=[
                "currency_uuid",
                "long_name",
                "short_name",
                "currency_type",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        
        with self._get_connection() as connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to fetch currencies: {exc}") from exc
                
        currencies: list[TXCurrencyBase] = []
        for row in rows:
            currency = TXCurrencyBase(
                long_name=row["long_name"],
                short_name=row["short_name"],
                currency_type=TXCurrencyType(row["currency_type"]), 
                uuid=row["currency_uuid"],
            )
            currencies.append(currency)
        return currencies

    def insert_currency(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new currency into the storage and return its UUID.

        Creates a new currency record in the database with the provided information.
        Automatically generates a UUID if not provided.

        Args:
            long_name (str): The full name of the currency (e.g., "Bitcoin").
            short_name (str): The abbreviated name or symbol (e.g., "BTC").
            currency_type (TXCurrencyType): The type of currency (FIAT, CRYPTO, etc.).
            uuid (Optional[str]): Currency UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created currency.

        Raises:
            RuntimeError: If the database insert operation fails.

        Example:
            >>> currency_uuid = storage.insert_currency(
            ...     long_name="Bitcoin",
            ...     short_name="BTC",
            ...     currency_type=TXCurrencyType.CRYPTO
            ... )
        """
        currency_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "currency_uuid": currency_uuid,
            "long_name": long_name,
            "short_name": short_name,
            "currency_type": currency_type.value,
        }
        sql, params = TXSQLBuilder.insert(
            table="currency",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert currency: {exc}") from exc
        return currency_uuid

    def update_currency(
        self,
        uuid: str,
        long_name: Optional[str] = None,
        short_name: Optional[str] = None,
        currency_type: Optional[TXCurrencyType] = None
    ) -> None:
        """Update an existing currency in the storage.

        Updates currency information in the database. Only provided parameters will be updated;
        None values are ignored, allowing for partial updates.

        Args:
            uuid (str): The UUID of the currency to update.
            long_name (Optional[str]): New full name of the currency.
            short_name (Optional[str]): New abbreviated name or symbol.
            currency_type (Optional[TXCurrencyType]): New currency type.

        Raises:
            RuntimeError: If the database update operation fails.

        Example:
            >>> storage.update_currency(
            ...     uuid="currency-123",
            ...     long_name="Bitcoin Cash",
            ...     short_name="BCH"
            ... )
        """
        data: Dict[str, Any] = {}
        if long_name is not None:
            data["long_name"] = long_name
        if short_name is not None:
            data["short_name"] = short_name
        if currency_type is not None:
            data["currency_type"] = currency_type.value
        sql, params = TXSQLBuilder.update(
            table="currency",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update currency: {exc}") from exc

    def delete_currency(self, uuid: str) -> None:
        """Delete a currency from the storage (soft delete).

        Marks a currency as deleted by setting the deleted flag to 1. The currency record remains in the database but will be excluded from normal queries.

        Args:
            uuid (str): The UUID of the currency to delete.

        Raises:
            RuntimeError: If the database update operation fails.

        Note:
            This is a soft delete operation. The currency record is not physically removed from the database but marked as deleted.

        Example:
            >>> storage.delete_currency("currency-123")
        """
        sql, params = TXSQLBuilder.update(
            table="currency",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete currency: {exc}") from exc

    # --- EXCHANGE DATA SOURCE CRUD ---
    def get_exchange_data_sources(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXExchangeDataSourceBase]:
        """Retrieve exchange data sources matching the given query, sort, offset, and limit.

        Fetches exchange data source records from the database with optional filtering, sorting and pagination.
        Only returns non-deleted exchange data sources (soft deletion support).

        Args:
            query (Optional[TXQueryNode]): Query conditions for filtering exchange data sources. If None, returns all non-deleted sources.
            sort (Optional[list[TXSortCriterion]]): List of sort criteria for ordering results.
            offset (Optional[int]): Number of records to skip (for pagination).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            list[TXExchangeDataSourceBase]: List of TXExchangeDataSourceBase objects matching the criteria.

        Raises:
            RuntimeError: If the database query fails.

        Example:
            >>> # Get all sources that support cryptocurrency data
            >>> sources = storage.get_exchange_data_sources(limit=10)
        """
        sql, params = TXSQLBuilder.select(
            table="exchange_data_source",
            columns=[
                "exchange_data_source_uuid",
                "name",
                "available_currency_types",
                "default_for_types",
                "notes",
                "connection_data_required",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch exchange data sources: {exc}") from exc
        
        exchange_data_sources: list[TXExchangeDataSourceBase] = []
        for row in rows:
            # Parse the SET fields from MySQL
            available_currency_types = set()
            if row["available_currency_types"]:
                for currency_type in row["available_currency_types"].split(','):
                    available_currency_types.add(TXCurrencyType(currency_type))
            
            default_for_types = set()
            if row["default_for_types"]:
                for currency_type in row["default_for_types"].split(','):
                    default_for_types.add(TXCurrencyType(currency_type))
            
            exchange_data_source = TXExchangeDataSourceBase(
                uuid=row["exchange_data_source_uuid"]
            )
            exchange_data_source._name=row["name"]
            exchange_data_source._available_currency_types=available_currency_types
            exchange_data_source._connection_data_required=bool(row["connection_data_required"])
            exchange_data_source._default_for_types = default_for_types if default_for_types else None
            exchange_data_source.notes = row["notes"]
            exchange_data_sources.append(exchange_data_source)
        
        return exchange_data_sources

    def insert_exchange_data_source(
        self,
        name: str,
        available_currency_types: set[TXCurrencyType],
        connection_data_required: bool,
        default_for_types: Optional[set[TXCurrencyType]] = None,
        notes: Optional[str] = None,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new exchange data source into the storage and return its UUID.

        Creates a new exchange data source record in the database with the provided information.
        Automatically generates a UUID if not provided.

        Args:
            name (str): The name of the exchange data source (e.g., "CoinGecko").
            available_currency_types (set[TXCurrencyType]): Set of currency types this source supports.
            connection_data_required (bool): Whether this source requires connection data for access.
            default_for_types (Optional[set[TXCurrencyType]]): Set of currency types for which this source is the default.
            notes (Optional[str]): Optional additional notes about the data source.
            uuid (Optional[str]): Exchange data source UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created exchange data source.

        Raises:
            RuntimeError: If the database insert operation fails.

        Example:
            >>> source_uuid = storage.insert_exchange_data_source(
            ...     name="CoinGecko",
            ...     available_currency_types={TXCurrencyType.CRYPTO},
            ...     connection_data_required=False,
            ...     default_for_types={TXCurrencyType.CRYPTO}
            ... )
        """
        exchange_data_source_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
        # Convert sets to comma-separated strings for MySQL SET type
        available_types_str = ','.join([ct.value for ct in available_currency_types])
        default_types_str = ','.join([ct.value for ct in default_for_types]) if default_for_types else None
        
        data = {
            "exchange_data_source_uuid": exchange_data_source_uuid,
            "name": name,
            "available_currency_types": available_types_str,
            "default_for_types": default_types_str,
            "notes": notes,
            "connection_data_required": int(connection_data_required),
        }
        sql, params = TXSQLBuilder.insert(
            table="exchange_data_source",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert exchange data source: {exc}") from exc
        
        return exchange_data_source_uuid

    def update_exchange_data_source(
        self,
        uuid: str,
        name: Optional[str] = None,
        available_currency_types: Optional[set[TXCurrencyType]] = None,
        connection_data_required: Optional[bool] = None,
        default_for_types: Optional[set[TXCurrencyType]] = None,
        notes: Optional[str] = None
    ) -> None:
        """Update an existing exchange data source in the storage.

        Updates exchange data source information in the database. Only provided parameters will be updated;
        None values are ignored, allowing for partial updates.

        Args:
            uuid (str): The UUID of the exchange data source to update.
            name (Optional[str]): New name for the exchange data source.
            available_currency_types (Optional[set[TXCurrencyType]]): New set of supported currency types.
            connection_data_required (Optional[bool]): New connection data requirement flag.
            default_for_types (Optional[set[TXCurrencyType]]): New set of currency types for which this is the default source.
            notes (Optional[str]): New additional notes about the data source.

        Raises:
            RuntimeError: If the database update operation fails.

        Example:
            >>> storage.update_exchange_data_source(
            ...     uuid="source-123",
            ...     name="Updated CoinGecko",
            ...     notes="Updated API endpoint"
            ... )
        """
        data: Dict[str, Any] = {}
        
        if name is not None:
            data["name"] = name
        if available_currency_types is not None:
            data["available_currency_types"] = ','.join([ct.value for ct in available_currency_types])
        if connection_data_required is not None:
            data["connection_data_required"] = int(connection_data_required)
        if default_for_types is not None:
            data["default_for_types"] = ','.join([ct.value for ct in default_for_types]) if default_for_types else None
        if notes is not None:
            data["notes"] = notes
            
        sql, params = TXSQLBuilder.update(
            table="exchange_data_source",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update exchange data source: {exc}") from exc

    def delete_exchange_data_source(self, uuid: str) -> None:
        """Delete an exchange data source from the storage (soft delete).

        Marks an exchange data source as deleted by setting the deleted flag to 1. The record remains in the database but will be excluded from normal queries.

        Args:
            uuid (str): The UUID of the exchange data source to delete.

        Raises:
            RuntimeError: If the database update operation fails.

        Note:
            This is a soft delete operation. The exchange data source record is not physically removed from the database but marked as deleted.

        Example:
            >>> storage.delete_exchange_data_source("source-123")
        """
        sql, params = TXSQLBuilder.update(
            table="exchange_data_source",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete exchange data source: {exc}") from exc

    def get_currency_exchanges(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXCurrencyExchangeBase]:
        """
        Retrieve currency exchanges matching the given query, sort, offset, and limit.
        Returns a list of TXCurrencyExchangeBase objects.
        """
        sql, params = TXSQLBuilder.select(
            table="currency_exchange",
            columns=[
                "currency_exchange_uuid",
                "currency_uuid_source",
                "currency_uuid_target",
                "exchange_data_source_uuid",
                "value",
                "UNIX_TIMESTAMP(datetime) AS datetime_ts"
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch currency exchanges: {exc}") from exc        
        currency_exchanges: list[TXCurrencyExchangeBase] = []
        for row in rows:
            # Get source currency
            source_currency = self.get_currencies(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid_source"])
            )[0]            
            # Get target currency
            target_currency = self.get_currencies(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid_target"])
            )[0]
            exchange = TXCurrencyExchangeBase(
                currency_source=source_currency,
                currency_target=target_currency,
                value=float(row["value"]),
                datetime=int(row["datetime_ts"]),
                uuid=row["currency_exchange_uuid"]
            )            
            # Set data source if available
            if row["exchange_data_source_uuid"]:
                exchange.data_source = self.get_exchange_data_sources(
                    TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", row["exchange_data_source_uuid"])
                )[0]            
            currency_exchanges.append(exchange)        
        return currency_exchanges

    def insert_currency_exchange(
        self,
        currency_uuid_source: str,
        currency_uuid_target: str,
        value: float,
        exchange_data_source_uuid: Optional[str] = None,
        date_time: Optional[int] = None,
        uuid: Optional[str] = None
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
        currency_exchange_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data={
            "currency_exchange_uuid": currency_exchange_uuid,
            "currency_uuid_source": currency_uuid_source,
            "currency_uuid_target": currency_uuid_target,
            "exchange_data_source_uuid": exchange_data_source_uuid,
            "value": value
        }
        if date_time is not None:
            data["datetime"] = dt.fromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S')
        sql, params = TXSQLBuilder.insert(
            table="currency_exchange",
            data=data
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert currency exchange: {exc}") from exc
        
        return currency_exchange_uuid

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
        """
        data: Dict[str, Any] = {}
        
        if currency_uuid_source is not None:
            data["currency_uuid_source"] = currency_uuid_source
        if currency_uuid_target is not None:
            data["currency_uuid_target"] = currency_uuid_target
        if value is not None:
            data["value"] = value
        if exchange_data_source_uuid is not None:
            data["exchange_data_source_uuid"] = exchange_data_source_uuid
        if date_time is not None:
            data["datetime"] = dt.fromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S')                 
        sql, params = TXSQLBuilder.update(
            table="currency_exchange",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update currency exchange: {exc}") from exc

    def delete_currency_exchange(self, uuid: str) -> None:
        """
        Delete a currency exchange from the storage.

        Args:
            uuid: The UUID of the currency exchange to delete.
        """
        sql, params = TXSQLBuilder.delete(
            table="currency_exchange",
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete currency exchange: {exc}") from exc

    # --- EXCHANGE DATA SOURCE CONNECTION DATA CRUD ---
    def get_exchange_data_source_connection_data(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXExchangeDataSourceConnectionDataBase]:
        """
        Retrieve connection data entries with optional filtering, ordering, and pagination.
        Returns a list of TXExchangeDataSourceConnectionDataBase objects.
        """
        sql, params = TXSQLBuilder.select(
            table="exchange_data_source_connection_data",
            columns=[
                "exchange_data_source_connection_data_uuid",
                "exchange_data_source_uuid",
                "user_uuid",
                "connection_data",
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch exchange data source connection data: {exc}") from exc
        results: list[TXExchangeDataSourceConnectionDataBase] = []
        for row in rows:
            user = self.get_users(
                TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"])
            )[0]
            data_source = self.get_exchange_data_sources(
                TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", row["exchange_data_source_uuid"])
            )[0]
            conn = TXExchangeDataSourceConnectionDataBase(
                user=user,
                data_source=data_source,
                connection_data=row["connection_data"],
                uuid=row["exchange_data_source_connection_data_uuid"],
            )
            results.append(conn)
        return results

    def insert_exchange_data_source_connection_data(
        self,
        exchange_data_source_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new connection data entry and return its UUID."""
        TXUtils.validate_json(connection_data)
        conn_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        sql, params = TXSQLBuilder.insert(
            table="exchange_data_source_connection_data",
            data={
                "exchange_data_source_connection_data_uuid": conn_uuid,
                "exchange_data_source_uuid": exchange_data_source_uuid,
                "user_uuid": user_uuid,
                "connection_data": connection_data,
            },
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert exchange data source connection data: {exc}") from exc
        return conn_uuid

    def update_exchange_data_source_connection_data(
        self,
        uuid: str,
        exchange_data_source_uuid: Optional[str] = None,
        user_uuid: Optional[str] = None,
        connection_data: Optional[str] = None
    ) -> None:
        """Update an existing connection data entry by UUID.
        
        For connection_data, performs selective merge:
        - Retrieves existing JSON data from database
        - Merges new JSON data with existing data
        - Preserves existing values not specified in new data
        - Updates only the values specified in new data
        """
        data: Dict[str, Any] = {}        
        if exchange_data_source_uuid is not None:
            data["exchange_data_source_uuid"] = exchange_data_source_uuid
        if user_uuid is not None:
            data["user_uuid"] = user_uuid            
        if connection_data is not None:
            # Validate the new JSON data
            TXUtils.validate_json(connection_data)            
            try:
                # Parse the new JSON data
                new_data = json.loads(connection_data)                
                # Retrieve existing connection data from database
                existing_sql, existing_params = TXSQLBuilder.select(
                    table="exchange_data_source_connection_data",
                    columns=["connection_data"],
                    where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_connection_data_uuid", uuid),
                )                
                with self._get_connection() as connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(existing_sql, existing_params)
                    existing_row = cursor.fetchone()
                    cursor.close()
                if existing_row is None:
                    raise ValueError(f"No connection data found with UUID: {uuid}")                
                existing_connection_data = existing_row["connection_data"]                
                # Handle case where existing data is None or empty
                if existing_connection_data:
                    try:
                        existing_data = json.loads(existing_connection_data)
                        # Ensure existing_data is a dictionary for merging
                        if not isinstance(existing_data, dict):
                            existing_data = {}
                    except (json.JSONDecodeError, TypeError):
                        # If existing data is malformed, start with empty dict
                        existing_data = {}
                else:
                    existing_data = {}                
                # Perform selective merge: existing data + new data
                # New data values override existing ones, but existing values are preserved
                if isinstance(new_data, dict) and isinstance(existing_data, dict):
                    merged_data = existing_data.copy()
                    # Perform selective merge: preserve existing values, update/add new ones
                    merged_data = TXUtils.merge_dict(merged_data, new_data)
                    data["connection_data"] = json.dumps(merged_data)
                else:
                    # If new_data is not a dict, replace entirely (fallback behavior)
                    data["connection_data"] = connection_data                    
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in connection_data: {exc}") from exc
            except MySQLError as exc:
                raise RuntimeError(f"Failed to retrieve existing connection data: {exc}") from exc
            except Exception as exc:
                raise RuntimeError(f"Unexpected error during connection data merge: {exc}") from exc        
        # Proceed with update only if there's data to update
        if data:
            sql, params = TXSQLBuilder.update(
                table="exchange_data_source_connection_data",
                data=data,
                where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_connection_data_uuid", uuid),
            )
            try:
                with self._get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute(sql, params)
                    connection.commit()
                    cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to update exchange data source connection data: {exc}") from exc

    def delete_exchange_data_source_connection_data(self, uuid: str) -> None:
        """Delete a connection data entry by UUID (no soft-delete column)."""
        sql, params = TXSQLBuilder.delete(
            table="exchange_data_source_connection_data",
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_connection_data_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete exchange data source connection data: {exc}") from exc


    # --- FINANCIAL HUB CRUD ---
    def get_financial_hubs(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXFinancialHubBase]:
        """
        Retrieve financial hubs matching the given query, sort, offset, and limit.
        Returns a list of TXFinancialHubBase objects.
        """
        sql, params = TXSQLBuilder.select(
            table="financial_hub",
            columns=[
                "financial_hub_uuid",
                "name",
                "allowed_operations",
                "notes",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch financial hubs: {exc}") from exc
        hubs: list[TXFinancialHubBase] = []
        for row in rows:
            ops: set[TXAssetType] = set()
            if row["allowed_operations"]:
                for op in row["allowed_operations"].split(','):
                    ops.add(TXAssetType(op))
            hub = TXFinancialHubBase(
                uuid=row["financial_hub_uuid"]
            )
            hub._name=row["name"]
            hub._allowed_operations=ops
            hub.notes = row.get("notes")
            hubs.append(hub)
        return hubs

    def insert_financial_hub(
        self,
        name: str,
        allowed_operations: set[TXAssetType],
        notes: Optional[str] = None,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new financial hub into the storage and return its UUID.

        Creates a new financial hub record in the database with the provided information.
        Automatically generates a UUID if not provided.

        Args:
            name (str): The name of the financial hub (e.g., "Binance", "Coinbase").
            allowed_operations (set[TXAssetType]): Set of asset types this hub supports for operations.
            notes (Optional[str]): Optional additional notes about the financial hub.
            uuid (Optional[str]): Financial hub UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created financial hub.

        Raises:
            RuntimeError: If the database insert operation fails.

        Example:
            >>> hub_uuid = storage.insert_financial_hub(
            ...     name="Binance",
            ...     allowed_operations={TXAssetType.CRYPTO, TXAssetType.FIAT},
            ...     notes="Major cryptocurrency exchange"
            ... )
        """
        hub_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        ops_str = ','.join([op.value for op in allowed_operations])
        data = {
            "financial_hub_uuid": hub_uuid,
            "name": name,
            "allowed_operations": ops_str,
            "notes": notes,
        }
        sql, params = TXSQLBuilder.insert(
            table="financial_hub",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert financial hub: {exc}") from exc
        return hub_uuid

    def update_financial_hub(
        self,
        uuid: str,
        name: Optional[str] = None,
        allowed_operations: Optional[set[TXAssetType]] = None,
        notes: Optional[str] = None
    ) -> None:
        """Update an existing financial hub in the storage.

        Updates financial hub information in the database. Only provided parameters will be updated;
        None values are ignored, allowing for partial updates.

        Args:
            uuid (str): The UUID of the financial hub to update.
            name (Optional[str]): New name for the financial hub.
            allowed_operations (Optional[set[TXAssetType]]): New set of supported asset types.
            notes (Optional[str]): New additional notes about the financial hub.

        Raises:
            RuntimeError: If the database update operation fails.

        Example:
            >>> storage.update_financial_hub(
            ...     uuid="hub-123",
            ...     name="Updated Binance",
            ...     notes="Updated exchange information"
            ... )
        """
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if allowed_operations is not None:
            data["allowed_operations"] = ','.join([op.value for op in allowed_operations])
        if notes is not None:
            data["notes"] = notes
        sql, params = TXSQLBuilder.update(
            table="financial_hub",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update financial hub: {exc}") from exc

    def delete_financial_hub(self, uuid: str) -> None:
        """Soft-delete a financial hub by setting deleted = 1."""
        sql, params = TXSQLBuilder.update(
            table="financial_hub",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete financial hub: {exc}") from exc

    # --- FINANCIAL HUB CONNECTION DATA CRUD ---
    def get_financial_hub_connection_data(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXFinancialHubConnectionDataBase]:
        """
        Retrieve financial hub connection data with optional filtering, ordering, and pagination.
        Returns a list of TXFinancialHubConnectionDataBase objects.
        """
        sql, params = TXSQLBuilder.select(
            table="financial_hub_connection_data",
            columns=[
                "financial_hub_connection_data_uuid",
                "financial_hub_uuid",
                "user_uuid",
                "connection_data",
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch financial hub connection data: {exc}") from exc
        results: list[TXFinancialHubConnectionDataBase] = []
        for row in rows:
            user = self.get_users(
                TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"])
            )[0]
            hub = self.get_financial_hubs(
                TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", row["financial_hub_uuid"])
            )[0]
            conn = TXFinancialHubConnectionDataBase(
                user=user,
                financial_hub=hub,
                connection_data=row["connection_data"],
                uuid=row["financial_hub_connection_data_uuid"],
            )
            results.append(conn)
        return results

    def insert_financial_hub_connection_data(
        self,
        financial_hub_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new financial hub connection data row and return its UUID."""
        TXUtils.validate_json(connection_data)
        conn_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "financial_hub_connection_data_uuid": conn_uuid,
            "financial_hub_uuid": financial_hub_uuid,
            "user_uuid": user_uuid,
            "connection_data": connection_data,
        }
        sql, params = TXSQLBuilder.insert(
            table="financial_hub_connection_data",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert financial hub connection data: {exc}") from exc
        return conn_uuid

    def update_financial_hub_connection_data(
        self,
        uuid: str,
        financial_hub_uuid: Optional[str] = None,
        user_uuid: Optional[str] = None,
        connection_data: Optional[str] = None
    ) -> None:
        """Update an existing financial hub connection data row by UUID.
        
        For connection_data, performs a selective merge:
        - Preserves existing JSON values not specified in the new data
        - Updates only the values specified in the new JSON string
        - Adds new values from the new JSON that don't exist in the existing data
        """
        data: Dict[str, Any] = {}
        if financial_hub_uuid is not None:
            data["financial_hub_uuid"] = financial_hub_uuid
        if user_uuid is not None:
            data["user_uuid"] = user_uuid        
        if connection_data is not None:
            TXUtils.validate_json(connection_data)            
            # Retrieve existing connection_data for selective merge
            try:
                sql_select, params_select = TXSQLBuilder.select(
                    table="financial_hub_connection_data",
                    columns=["connection_data"],
                    where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_connection_data_uuid", uuid),
                )
                with self._get_connection() as connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(sql_select, params_select)
                    existing_row = cursor.fetchone()
                    cursor.close()
                if existing_row is None:
                    raise RuntimeError(f"Financial hub connection data with UUID {uuid} not found")                
                existing_connection_data = existing_row["connection_data"]
                # Parse existing and new JSON data
                try:
                    existing_json = json.loads(existing_connection_data) if existing_connection_data else {}
                except json.JSONDecodeError:
                    # If existing data is malformed, treat as empty dict
                    existing_json = {}                
                try:
                    new_json = json.loads(connection_data)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in connection_data: {exc}") from exc
                if isinstance(new_json, dict) and isinstance(existing_json, dict):
                    # Perform selective merge: preserve existing values, update/add new ones
                    merged_json = TXUtils.merge_dict(existing_json, new_json)                    
                    # Convert back to JSON string
                    data["connection_data"] = json.dumps(merged_json, separators=(',', ':'))
                else:
                    # If new_data is not a dict, replace entirely (fallback behavior)
                    data["connection_data"] = connection_data
            except MySQLError as exc:
                raise RuntimeError(f"Failed to retrieve existing connection data for merge: {exc}") from exc        
        # Proceed with update only if there's data to update
        if data:
            sql, params = TXSQLBuilder.update(
                table="financial_hub_connection_data",
                data=data,
                where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_connection_data_uuid", uuid),
            )
            try:
                with self._get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute(sql, params)
                    connection.commit()
                    cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to update financial hub connection data: {exc}") from exc

    def delete_financial_hub_connection_data(self, uuid: str) -> None:
        """Delete a financial hub connection data row by UUID."""
        sql, params = TXSQLBuilder.delete(
            table="financial_hub_connection_data",
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_connection_data_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete financial hub connection data: {exc}") from exc

    # --- WALLET CRUD ---
    def get_wallets(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXWalletBase]:
        """
        Retrieve wallets matching the given query, sort, offset, and limit.
        Returns a list of TXWalletBase objects.
        """
        base_where = TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)
        where = base_where if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, base_where)
        sql, params = TXSQLBuilder.select(
            table="wallet",
            columns=[
                "wallet_uuid",
                "user_uuid",
                "financial_hub_uuid",
                "currency_uuid",
                "name",
                "details_data",
                "content_type",
                "UNIX_TIMESTAMP(initial_value_datetime) AS initial_ts",
                "total_value",
                "UNIX_TIMESTAMP(total_value_datetime) AS total_ts",
                "connection_data",
            ],
            where=where,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch wallets: {exc}") from exc
        wallets: list[TXWalletBase] = []
        for row in rows:
            user = self.get_users(TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"]))[0]
            hub = self.get_financial_hubs(TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", row["financial_hub_uuid"]))[0]
            currency = None
            if row.get("currency_uuid"):
                currency = self.get_currencies(TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid"]))[0]
            wallet = TXWalletBase(
                user=user,
                financial_hub=hub,
                currency=currency,
                name=row["name"],
                content_type=TXAssetType(row["content_type"]),
                uuid=row["wallet_uuid"],
            )
            # Optional fields
            if row.get("details_data") is not None:
                wallet.details_data = row["details_data"]
            if row.get("initial_ts") is not None:
                wallet.initial_value_datetime = int(row["initial_ts"])            
            if row.get("total_value") is not None:
                wallet.total_value = float(row["total_value"])
            if row.get("total_ts") is not None:
                wallet.total_value_datetime = int(row["total_ts"])            
            if row.get("connection_data") is not None:
                wallet.connection_data = row["connection_data"]
            wallets.append(wallet)
        return wallets

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
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new wallet into the storage and return its UUID.

        Creates a new wallet record in the database with the provided information.
        Automatically generates a UUID if not provided. Validates JSON data if provided.

        Args:
            user_uuid (str): The UUID of the user who owns this wallet.
            financial_hub_uuid (str): The UUID of the financial hub where this wallet is hosted.
            name (str): The display name for the wallet.
            content_type (TXAssetType): The type of assets this wallet contains.
            currency_uuid (Optional[str]): The UUID of the primary currency for this wallet.
            details_data (Optional[str]): JSON string containing additional wallet details.
            initial_value (Optional[float]): The initial value of the wallet.
            initial_value_datetime (Optional[int]): Unix timestamp of when the initial value was set.
            total_value (Optional[float]): The current total value of the wallet.
            total_value_datetime (Optional[int]): Unix timestamp of when the total value was last updated.
            connection_data (Optional[str]): JSON string containing connection information for the wallet.
            uuid (Optional[str]): Wallet UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created wallet.

        Raises:
            RuntimeError: If the database insert operation fails.
            ValueError: If provided JSON data is invalid.

        Example:
            >>> wallet_uuid = storage.insert_wallet(
            ...     user_uuid="user-123",
            ...     financial_hub_uuid="hub-456",
            ...     name="My Bitcoin Wallet",
            ...     content_type=TXAssetType.CRYPTO,
            ...     currency_uuid="btc-uuid"
            ... )
        """
        if details_data is not None:
            TXUtils.validate_json(details_data)
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
        wallet_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data: Dict[str, Any] = {
            "wallet_uuid": wallet_uuid,
            "user_uuid": user_uuid,
            "financial_hub_uuid": financial_hub_uuid,
            "currency_uuid": currency_uuid,
            "name": name,
            "details_data": details_data,
            "content_type": content_type.value,
            "total_value": total_value,
            "connection_data": connection_data,
        }
        if initial_value_datetime is not None:
            data["initial_value_datetime"] = dt.fromtimestamp(initial_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if total_value_datetime is not None:
            data["total_value_datetime"] = dt.fromtimestamp(total_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        sql, params = TXSQLBuilder.insert(
            table="wallet",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert wallet: {exc}") from exc
        return wallet_uuid

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
        """Update an existing wallet in the storage.

        Updates wallet information in the database. Only provided parameters will be updated;
        None values are ignored, allowing for partial updates. Validates JSON data if provided.

        Args:
            uuid (str): The UUID of the wallet to update.
            user_uuid (Optional[str]): New owner user UUID.
            financial_hub_uuid (Optional[str]): New financial hub UUID.
            name (Optional[str]): New display name for the wallet.
            content_type (Optional[TXAssetType]): New asset type for the wallet.
            currency_uuid (Optional[str]): New primary currency UUID.
            details_data (Optional[str]): New JSON string containing wallet details.
            initial_value (Optional[float]): New initial value of the wallet.
            initial_value_datetime (Optional[int]): New Unix timestamp for initial value.
            total_value (Optional[float]): New current total value of the wallet.
            total_value_datetime (Optional[int]): New Unix timestamp for total value update.
            connection_data (Optional[str]): New JSON string containing connection information.

        Raises:
            RuntimeError: If the database update operation fails.
            ValueError: If provided JSON data is invalid.

        Example:
            >>> storage.update_wallet(
            ...     uuid="wallet-123",
            ...     name="Updated Wallet Name",
            ...     total_value=1500.50
            ... )
        """
        data: Dict[str, Any] = {}
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if financial_hub_uuid is not None:
            data["financial_hub_uuid"] = financial_hub_uuid
        if name is not None:
            data["name"] = name
        if content_type is not None:
            data["content_type"] = content_type.value
        if currency_uuid is not None:
            data["currency_uuid"] = currency_uuid
        if details_data is not None:
            TXUtils.validate_json(details_data)
            data["details_data"] = details_data

        if initial_value_datetime is not None:
            data["initial_value_datetime"] = dt.fromtimestamp(initial_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if total_value is not None:
            data["total_value"] = total_value
        if total_value_datetime is not None:
            data["total_value_datetime"] = dt.fromtimestamp(total_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
            data["connection_data"] = connection_data
        sql, params = TXSQLBuilder.update(
            table="wallet",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update wallet: {exc}") from exc

    def delete_wallet(self, uuid: str) -> None:
        """Delete a wallet from the storage (soft delete).

        Marks a wallet as deleted by setting the deleted flag to 1. The wallet record remains in the database but will be excluded from normal queries.

        Args:
            uuid (str): The UUID of the wallet to delete.

        Raises:
            RuntimeError: If the database update operation fails.

        Note:
            This is a soft delete operation. The wallet record is not physically removed from the database but marked as deleted.

        Example:
            >>> storage.delete_wallet("wallet-123")
        """
        sql, params = TXSQLBuilder.update(
            table="wallet",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete wallet: {exc}") from exc

    # --- TRANSACTION CRUD ---
    def get_transactions(
        self,
        query: Optional[TXQueryNode] = None,
        sort: Optional[list[TXSortCriterion]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[TXTransactionBase]:
        """
        Retrieve transactions matching the given query, sort, offset, and limit.
        Returns a list of TXTransactionBase objects.
        """
        base_where = TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)
        where = base_where if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, base_where)
        sql, params = TXSQLBuilder.select(
            table="transaction",
            columns=[
                "transaction_uuid",
                "origin_transaction_uuid",
                "source_wallet_uuid",
                "target_wallet_uuid",
                "bot_uuid",
                "UNIX_TIMESTAMP(start_datetime) AS start_ts",
                "UNIX_TIMESTAMP(end_datetime) AS end_ts",
                "operational_mode",
                "source_value",
                "target_value",
                "status",
                "annotations",
                "`order`",
            ],
            where=where,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch transactions: {exc}") from exc
        
        transactions: list[TXTransactionBase] = []
        for row in rows:
            transaction = TXTransactionBase(uuid=row["transaction_uuid"])
            
            # Set origin transaction if available
            if row.get("origin_transaction_uuid"):
                origin_transactions = self.get_transactions(
                    TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", row["origin_transaction_uuid"])
                )
                if len(origin_transactions) == 1:
                    transaction.origin_transaction = origin_transactions[0]
            
            # Set source wallet if available
            if row.get("source_wallet_uuid"):
                source_wallets = self.get_wallets(
                    TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", row["source_wallet_uuid"])
                )
                if len(source_wallets) == 1:
                    transaction.source_wallet = source_wallets[0]
            
            # Set target wallet if available
            if row.get("target_wallet_uuid"):
                target_wallets = self.get_wallets(
                    TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", row["target_wallet_uuid"])
                )
                if len(target_wallets) == 1:
                    transaction.target_wallet = target_wallets[0]
            
            # Set bot if available
            if row.get("bot_uuid"):
                bots = self.get_bots(
                    TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", row["bot_uuid"])
                )
                if len(bots) == 1:
                    transaction.bot = bots[0]
            
            # Set timestamps
            if row.get("start_ts") is not None:
                transaction.start_datetime = int(row["start_ts"])
            if row.get("end_ts") is not None:
                transaction.end_datetime = int(row["end_ts"])
            
            # Set operational mode
            if row.get("operational_mode"):
                transaction.operational_mode = TXTransOperationalMode(row["operational_mode"])
            
            # Set values
            if row.get("source_value") is not None:
                transaction.source_value = float(row["source_value"])
            if row.get("target_value") is not None:
                transaction.target_value = float(row["target_value"])
            
            # Set status
            if row.get("status"):
                transaction.status = TXTransStatus(row["status"])
            
            # Set optional fields
            if row.get("annotations") is not None:
                transaction.annotations = row["annotations"]
            if row.get("order") is not None:
                transaction.order = int(row["order"])
            
            transactions.append(transaction)
        
        return transactions

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
        order: Optional[int] = None,
        uuid: Optional[str] = None
    ) -> str:
        """Insert a new transaction into the storage and return its UUID.

        Creates a new transaction record in the database with the provided information.
        Automatically generates a UUID if not provided.

        Args:
            origin_transaction_uuid (Optional[str]): UUID of the original transaction if this is a related transaction.
            source_wallet_uuid (Optional[str]): UUID of the wallet from which assets are transferred.
            target_wallet_uuid (Optional[str]): UUID of the wallet to which assets are transferred.
            bot_uuid (Optional[str]): UUID of the bot that initiated this transaction.
            start_datetime (Optional[int]): Unix timestamp when the transaction started.
            end_datetime (Optional[int]): Unix timestamp when the transaction completed.
            operational_mode (Optional[TXTransOperationalMode]): The operational mode of the transaction.
            source_value (Optional[float]): The value of assets in the source wallet.
            target_value (Optional[float]): The value of assets in the target wallet.
            status (Optional[TXTransStatus]): The current status of the transaction.
            annotations (Optional[str]): Additional notes or metadata about the transaction.
            order (Optional[int]): Order number for transaction sequencing.
            uuid (Optional[str]): Transaction UUID (auto-generated if None).

        Returns:
            str: The UUID of the newly created transaction.

        Raises:
            RuntimeError: If the database insert operation fails.

        Example:
            >>> transaction_uuid = storage.insert_transaction(
            ...     source_wallet_uuid="wallet-123",
            ...     target_wallet_uuid="wallet-456",
            ...     source_value=100.0,
            ...     target_value=0.001,
            ...     status=TXTransStatus.PENDING
            ... )
        """
        transaction_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data: Dict[str, Any] = {
            "transaction_uuid": transaction_uuid,
            "origin_transaction_uuid": origin_transaction_uuid,
            "source_wallet_uuid": source_wallet_uuid,
            "target_wallet_uuid": target_wallet_uuid,
            "bot_uuid": bot_uuid,
            "source_value": source_value,
            "target_value": target_value,
            "annotations": annotations,
            "order": order,
        }
        
        if start_datetime is not None:
            data["start_datetime"] = dt.fromtimestamp(start_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if end_datetime is not None:
            data["end_datetime"] = dt.fromtimestamp(end_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if operational_mode is not None:
            data["operational_mode"] = operational_mode.value
        if status is not None:
            data["status"] = status.value
        
        sql, params = TXSQLBuilder.insert(
            table="transaction",
            data=data,
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert transaction: {exc}") from exc
        
        return transaction_uuid

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
        """Update an existing transaction by UUID."""
        data: Dict[str, Any] = {}
        if origin_transaction_uuid is not None:
            data["origin_transaction_uuid"] = origin_transaction_uuid
        if source_wallet_uuid is not None:
            data["source_wallet_uuid"] = source_wallet_uuid
        if target_wallet_uuid is not None:
            data["target_wallet_uuid"] = target_wallet_uuid
        if bot_uuid is not None:
            data["bot_uuid"] = bot_uuid
        if start_datetime is not None:
            data["start_datetime"] = dt.fromtimestamp(start_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if end_datetime is not None:
            data["end_datetime"] = dt.fromtimestamp(end_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if operational_mode is not None:
            data["operational_mode"] = operational_mode.value
        if source_value is not None:
            data["source_value"] = source_value
        if target_value is not None:
            data["target_value"] = target_value
        if status is not None:
            data["status"] = status.value
        if annotations is not None:
            data["annotations"] = annotations
        if order is not None:
            data["order"] = order
        
        sql, params = TXSQLBuilder.update(
            table="transaction",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update transaction: {exc}") from exc

    def delete_transaction(self, uuid: str) -> None:
        """Soft-delete a transaction by setting deleted = 1."""
        sql, params = TXSQLBuilder.delete(
            table="transaction",
            where=TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", uuid),
        )
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, params)
                connection.commit()
                cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete transaction: {exc}") from exc
