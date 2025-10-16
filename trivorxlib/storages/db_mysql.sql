/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

CREATE TABLE IF NOT EXISTS `asset` (
  `id_asset` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `asset_uuid` varchar(128) NOT NULL,
  `long_name` varchar(100) NOT NULL,
  `short_name` varchar(50) NOT NULL,
  PRIMARY KEY (`id_asset`),
  UNIQUE KEY `asset_uuid_key` (`asset_uuid`),
  UNIQUE KEY `short_name` (`short_name`),
  KEY `asset_uuid` (`asset_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `bot` (
  `id_bot` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `bot_uuid` varchar(128) NOT NULL,
  `user_uuid` varchar(128) NOT NULL,
  `algo_uuid` varchar(128) NOT NULL,
  `name` varchar(200) NOT NULL,
  `algo_name` varchar(128) NOT NULL,
  `algo_version` varchar(20) NOT NULL,
  `algo_settings` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `annotations` text DEFAULT NULL,
  `active` tinyint(1) unsigned NOT NULL DEFAULT 0,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT 0,
  `creation_datetime` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_bot`),
  UNIQUE KEY `bot_uuid` (`bot_uuid`),
  KEY `bot_uuid_key` (`bot_uuid`),
  KEY `user_uuid` (`user_uuid`),
  KEY `algo_version` (`algo_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `currency` (
  `id_currency` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `currency_uuid` varchar(128) NOT NULL,
  `long_name` varchar(50) NOT NULL,
  `short_name` varchar(10) NOT NULL,
  `currency_type` enum('FIAT','CRYPTO') NOT NULL,
  PRIMARY KEY (`id_currency`),
  UNIQUE KEY `currency_uuid` (`currency_uuid`),
  KEY `currency_uuid_key` (`currency_uuid`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `currency_exchange` (
  `id_currency_exchange` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `currency_exchange_uuid` varchar(128) NOT NULL,
  `currency_uuid_source` varchar(128) NOT NULL,
  `currency_uuid_target` varchar(128) NOT NULL,
  `exchange_data_source_uuid` varchar(128) DEFAULT NULL,
  `value` decimal(25,13) unsigned NOT NULL,
  `datetime` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id_currency_exchange`),
  UNIQUE KEY `currency_exchange_uuid` (`currency_exchange_uuid`),
  KEY `currency_uuid_source` (`currency_uuid_source`),
  KEY `currency_uuid_target` (`currency_uuid_target`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `exchange_data_source` (
  `id_exchange_data_source_uuid` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `exchange_data_source_uuid` varchar(128) NOT NULL,
  `name` varchar(250) NOT NULL,
  `avaiable_currency_types` set('FIAT','CRYPTO') NOT NULL,
  `default_for_types` set('FIAT','CRYPTO') NOT NULL,
  `notes` text DEFAULT NULL,
  `connection_data_required` tinyint(1) unsigned NOT NULL,
  PRIMARY KEY (`id_exchange_data_source_uuid`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `exchange_data_source_uuid` (`exchange_data_source_uuid`),
  KEY `exchange_data_source_uuid_key` (`exchange_data_source_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `exchange_data_source_connection_data` (
  `id_exchange_data_source_connection_data` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `exchange_data_source_connection_data_uuid` varchar(128) NOT NULL,
  `exchange_data_source_uuid` varchar(128) NOT NULL,
  `user_uuid` varchar(128) NOT NULL,
  `connection_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id_exchange_data_source_connection_data`),
  UNIQUE KEY `exchange_data_source_uuid_user_uuid` (`exchange_data_source_uuid`,`user_uuid`),
  UNIQUE KEY `exchange_data_source_connection_data_uuid` (`exchange_data_source_connection_data_uuid`),
  KEY `exchange_data_source_uuid` (`exchange_data_source_uuid`),
  KEY `user_uuid` (`user_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `financial_hub` (
  `id_financial_hub` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `financial_hub_uuid` varchar(128) NOT NULL,
  `name` varchar(100) NOT NULL,
  `allowed_operations` set('ASSET','CURRENCY_FIAT','CURRENCY_CRYPTO') NOT NULL,
  `notes` text DEFAULT NULL,
  PRIMARY KEY (`id_financial_hub`),
  UNIQUE KEY `financial_hub_uuid` (`financial_hub_uuid`),
  UNIQUE KEY `name` (`name`),
  KEY `financial_hub_uuid_key` (`financial_hub_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `financial_hub_connection_data` (
  `id_financial_hub_connection_data` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `financial_hub_connection_data_uuid` varchar(128) NOT NULL,
  `financial_hub_uuid` varchar(128) NOT NULL,
  `user_uuid` varchar(128) NOT NULL,
  `connection_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id_financial_hub_connection_data`) USING BTREE,
  UNIQUE KEY `financial_hub_uuid_user_uuid` (`financial_hub_uuid`,`user_uuid`) USING BTREE,
  UNIQUE KEY `financial_hub_connection_data_uuid` (`financial_hub_connection_data_uuid`),
  KEY `financial_hub_uuid` (`financial_hub_uuid`) USING BTREE,
  KEY `user_uuid` (`user_uuid`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `transaction` (
  `id_transaction` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `transaction_uuid` varchar(128) NOT NULL,
  `origin_order_uuid` varchar(128) DEFAULT NULL,
  `source_wallet_uuid` varchar(128) DEFAULT NULL,
  `target_wallet_uuid` varchar(128) DEFAULT NULL,
  `bot_uuid` varchar(128) DEFAULT NULL,
  `start_datetime` timestamp NULL DEFAULT NULL,
  `end_datetime` timestamp NULL DEFAULT NULL,
  `operational_mode` enum('ORDER CREATION','TRANSFER','OTHER') DEFAULT NULL,
  `source_value` decimal(25,10) DEFAULT NULL,
  `target_value` decimal(25,10) DEFAULT NULL,
  `status` enum('WORKING','COMPLETED','CANCELED','FAILED','OTHER','UNKNOWN') DEFAULT NULL,
  `annotations` text DEFAULT NULL,
  `order` bigint(20) unsigned DEFAULT 0,
  PRIMARY KEY (`id_transaction`),
  UNIQUE KEY `transaction_uuid` (`transaction_uuid`),
  KEY `source_wallet_uuid` (`source_wallet_uuid`),
  KEY `target_wallet_uuid` (`target_wallet_uuid`),
  KEY `order` (`order`),
  KEY `bot_uuid` (`bot_uuid`),
  KEY `origin_order_uuid` (`origin_order_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `user` (
  `id_user` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_uuid` varchar(128) NOT NULL,
  `full_name` varchar(250) NOT NULL,
  `login` varchar(250) NOT NULL,
  `password` varchar(250) NOT NULL,
  `token` varchar(128) NOT NULL,
  `role` enum('ADMIN','STANDARD') NOT NULL DEFAULT 'STANDARD',
  `enabled` tinyint(1) unsigned NOT NULL DEFAULT 1,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT 0,
  `creation_datetime` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_user`),
  UNIQUE KEY `user_uuid` (`user_uuid`),
  UNIQUE KEY `login` (`login`),
  UNIQUE KEY `token` (`token`),
  KEY `user_uuid_key` (`user_uuid`),
  KEY `login_key` (`login`),
  KEY `token_key` (`token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

CREATE TABLE IF NOT EXISTS `wallet` (
  `id_wallet` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `wallet_uuid` varchar(128) NOT NULL,
  `user_uuid` varchar(128) NOT NULL,
  `financial_hub_uuid` varchar(128) NOT NULL,
  `asset_uuid` varchar(128) DEFAULT NULL,
  `currency_uuid` varchar(128) DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `details_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `content_type` enum('ASSET','CURRENCY_FIAT','CURRENCY_CRYPTO') NOT NULL,
  `initial_value` decimal(25,10) NOT NULL DEFAULT 0.0000000000,
  `initial_value_datetime` timestamp NOT NULL DEFAULT current_timestamp(),
  `total_value` decimal(25,10) NOT NULL DEFAULT 0.0000000000,
  `total_value_datetime` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `connection_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  PRIMARY KEY (`id_wallet`),
  UNIQUE KEY `wallet_uuid` (`wallet_uuid`),
  KEY `user_uuid` (`user_uuid`),
  KEY `financial_hub_uuid` (`financial_hub_uuid`),
  KEY `wallet_uuid_key` (`wallet_uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
