CREATE DATABASE IF NOT EXISTS telegabot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE telegabot;

CREATE TABLE IF NOT EXISTS telegram_accounts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    label VARCHAR(255) NOT NULL,
    phone VARCHAR(64) NULL,
    login VARCHAR(255) NULL,
    password_enc LONGBLOB NULL,
    twofa_enc LONGBLOB NULL,
    api_id INT NOT NULL,
    api_hash_enc LONGBLOB NULL,
    session_blob LONGBLOB NULL,
    session_version INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    meta JSON NULL,
    last_success_login_at DATETIME NULL,
    last_session_updated_at DATETIME NULL,
    last_error_at DATETIME NULL,
    last_error_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_account_status CHECK (status IN ('active', 'disabled', 'online', 'offline', 'error'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS actions_catalog (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    input_schema JSON NOT NULL,
    output_schema JSON NOT NULL,
    is_enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bot_rulesets (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT UNSIGNED NULL,
    name VARCHAR(255) NOT NULL,
    schedule_cron VARCHAR(255) NULL,
    rule_json JSON NOT NULL,
    allow_parallel_for_account TINYINT(1) NOT NULL DEFAULT 0,
    is_enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ruleset_account FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS jobs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ruleset_id BIGINT UNSIGNED NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    action_code VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    trigger_type VARCHAR(32) NOT NULL DEFAULT 'api',
    context_in JSON NOT NULL,
    context_out JSON NULL,
    current_step INT NULL,
    worker_id VARCHAR(64) NULL,
    heartbeat_at DATETIME NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_jobs_ruleset FOREIGN KEY (ruleset_id) REFERENCES bot_rulesets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_jobs_account FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_job_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'canceled'))
) ENGINE=InnoDB;

CREATE INDEX ix_jobs_status ON jobs(status);
CREATE INDEX ix_jobs_worker ON jobs(worker_id);
CREATE INDEX ix_jobs_heartbeat ON jobs(heartbeat_at);

CREATE TABLE IF NOT EXISTS job_steps (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    job_id BIGINT UNSIGNED NOT NULL,
    step_order INT NOT NULL,
    action_code VARCHAR(64) NOT NULL,
    input JSON NOT NULL,
    output JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    CONSTRAINT fk_job_steps_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_job_step_order UNIQUE (job_id, step_order),
    CONSTRAINT ck_job_step_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS action_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    job_id BIGINT UNSIGNED NULL,
    step_id BIGINT UNSIGNED NULL,
    account_id BIGINT UNSIGNED NULL,
    action_code VARCHAR(64) NULL,
    message VARCHAR(512) NOT NULL,
    level VARCHAR(16) NOT NULL DEFAULT 'info',
    payload JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_action_logs_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_action_logs_step FOREIGN KEY (step_id) REFERENCES job_steps(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_action_logs_account FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_action_log_level CHECK (level IN ('debug', 'info', 'warn', 'error'))
) ENGINE=InnoDB;

CREATE INDEX ix_action_logs_account ON action_logs(account_id);
CREATE INDEX ix_action_logs_created ON action_logs(created_at);

CREATE TABLE IF NOT EXISTS error_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    job_id BIGINT UNSIGNED NULL,
    step_id BIGINT UNSIGNED NULL,
    account_id BIGINT UNSIGNED NULL,
    error_code VARCHAR(128) NOT NULL,
    message TEXT NOT NULL,
    stack TEXT NULL,
    context JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_error_logs_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_error_logs_step FOREIGN KEY (step_id) REFERENCES job_steps(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_error_logs_account FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX ix_error_logs_account ON error_logs(account_id);
CREATE INDEX ix_error_logs_created ON error_logs(created_at);

INSERT INTO actions_catalog (code, input_schema, output_schema, is_enabled)
VALUES
    (
        'LOGIN',
        JSON_OBJECT('type', 'object', 'required', JSON_ARRAY('accountId'), 'properties', JSON_OBJECT('accountId', JSON_OBJECT('type', 'integer'))),
        JSON_OBJECT('type', 'object', 'properties', JSON_OBJECT('sessionOk', JSON_OBJECT('type', 'boolean'), 'accountId', JSON_OBJECT('type', 'integer'))),
        1
    ),
    (
        'LOGOUT',
        JSON_OBJECT('type', 'object', 'required', JSON_ARRAY('accountId'), 'properties', JSON_OBJECT('accountId', JSON_OBJECT('type', 'integer'))),
        JSON_OBJECT('type', 'object', 'properties', JSON_OBJECT('loggedOut', JSON_OBJECT('type', 'boolean'))),
        1
    ),
    (
        'OPEN_CHANNEL',
        JSON_OBJECT('type', 'object', 'required', JSON_ARRAY('accountId', 'channel', 'limit'), 'properties', JSON_OBJECT('accountId', JSON_OBJECT('type', 'integer'), 'channel', JSON_OBJECT('type', 'string'), 'limit', JSON_OBJECT('type', 'integer'))),
        JSON_OBJECT('type', 'object', 'properties', JSON_OBJECT('channel', JSON_OBJECT('type', 'string'), 'posts', JSON_OBJECT('type', 'array'), 'total', JSON_OBJECT('type', 'integer'))),
        1
    ),
    (
        'READ_POST',
        JSON_OBJECT('type', 'object', 'required', JSON_ARRAY('accountId', 'channel', 'postId'), 'properties', JSON_OBJECT('accountId', JSON_OBJECT('type', 'integer'), 'channel', JSON_OBJECT('type', 'string'), 'postId', JSON_OBJECT('type', 'string'))),
        JSON_OBJECT('type', 'object', 'properties', JSON_OBJECT('channel', JSON_OBJECT('type', 'string'), 'post', JSON_OBJECT('type', 'object'))),
        1
    )
ON DUPLICATE KEY UPDATE
    input_schema = VALUES(input_schema),
    output_schema = VALUES(output_schema),
    is_enabled = VALUES(is_enabled);
