CREATE DATABASE IF NOT EXISTS candidate_data;
USE candidate_data;

CREATE TABLE IF NOT EXISTS operations (
	operationId CHAR(36) NOT NULL PRIMARY KEY,
	amount DECIMAL(20,2) NOT NULL,
	currency CHAR(3) NOT NULL,
	description TEXT NULL DEFAULT NULL,
	status TINYINT NOT NULL DEFAULT 0,
	providerPaymentId CHAR(36) NULL DEFAULT NULL,
	isLockedForSubmit TINYINT NOT NULL DEFAULT 0,
	INDEX main (isLockedForSubmit,status)
);

CREATE TABLE IF NOT EXISTS events (
	id INT AUTO_INCREMENT PRIMARY KEY,
	operationId CHAR(36) NOT NULL,
	type TINYINT NOT NULL,
	fromStatus TINYINT NULL,
	toStatus TINYINT NOT NULL,
	occurredAt INT NOT NULL,
	message TEXT NULL DEFAULT NULL,
	INDEX operationId (operationId)
);

CREATE TABLE IF NOT EXISTS submits (
	id INT AUTO_INCREMENT PRIMARY KEY,
	operationId CHAR(36) NOT NULL,
	occurredAt INT NOT NULL,
	responseTimeMilliseconds INT NOT NULL DEFAULT 0,
	responseStatusCode INT NULL DEFAULT NULL,
	providerPaymentId CHAR(36) NULL DEFAULT NULL,
	status CHAR(30) NULL DEFAULT NULL,
	isRegularResponse TINYINT NOT NULL DEFAULT 0,
    exception TEXT NULL DEFAULT NULL,
	INDEX operationId (operationId)
);

CREATE TABLE IF NOT EXISTS receipts (
	id INT AUTO_INCREMENT PRIMARY KEY,
	providerPaymentId CHAR(36) NOT NULL,
	operationId CHAR(36) NOT NULL,
	receiptResult CHAR(30) NOT NULL,
	message TEXT NULL,
	rawOccurredAt CHAR(43),
	occurredAt INT NULL DEFAULT NULL,
	isIgnored TINYINT NOT NULL DEFAULT 0,
	INDEX occurredAt (occurredAt),
	INDEX operationId (operationId),
	INDEX providerPaymentId (providerPaymentId)
);
