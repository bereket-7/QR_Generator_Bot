-- Database Schema Updates for Phases 2, 3, and 4
-- Run these updates to support new features

-- Dynamic QR Codes Table
CREATE TABLE IF NOT EXISTS dynamic_qr_codes (
    qr_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    title TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    is_dynamic BOOLEAN DEFAULT 1,
    style_config TEXT,  -- JSON
    expiration TIMESTAMP,
    filepath TEXT NOT NULL,
    scan_count INTEGER DEFAULT 0,
    last_scan TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- QR Scans Table (Analytics)
CREATE TABLE IF NOT EXISTS qr_scans (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    qr_id TEXT NOT NULL,
    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    ip_address TEXT,
    referrer TEXT,
    device_type TEXT,
    browser TEXT,
    os TEXT,
    country TEXT,
    city TEXT,
    FOREIGN KEY (qr_id) REFERENCES dynamic_qr_codes (qr_id)
);

-- Batch QR Records Table
CREATE TABLE IF NOT EXISTS batch_qr_records (
    batch_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    total_items INTEGER NOT NULL,
    successful_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'processing',  -- processing, completed, failed
    metadata TEXT,  -- JSON
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- QR Templates Table
CREATE TABLE IF NOT EXISTS qr_templates (
    template_id TEXT PRIMARY KEY,
    user_id INTEGER,  -- NULL for system templates
    name TEXT NOT NULL,
    description TEXT,
    style_config TEXT NOT NULL,  -- JSON
    naming_pattern TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- Admin Roles and Permissions
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0;

-- Payment Sessions Table
CREATE TABLE IF NOT EXISTS payment_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    plan_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, completed, failed
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata TEXT,  -- JSON
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- User Subscriptions Table
CREATE TABLE IF NOT EXISTS user_subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id TEXT NOT NULL,
    stripe_customer_id TEXT NOT NULL,
    stripe_subscription_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- active, past_due, cancelled, expired
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    interval TEXT NOT NULL,  -- month, year
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    UNIQUE(user_id)  -- One active subscription per user
);

-- API Keys Table
CREATE TABLE IF NOT EXISTS api_keys (
    key_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,  -- Hashed API key
    permissions TEXT NOT NULL,  -- JSON array
    rate_limit INTEGER DEFAULT 1000,  -- Requests per hour
    expires_at TIMESTAMP,
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- System Configuration Table
CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users (user_id)
);

-- Audit Log Table (Enhanced)
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details TEXT,  -- JSON
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- Security Events Table
CREATE TABLE IF NOT EXISTS security_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,  -- login_attempt, permission_denied, etc.
    user_id INTEGER,
    username TEXT,
    ip_address TEXT,
    user_agent TEXT,
    details TEXT,  -- JSON
    severity TEXT DEFAULT 'medium',  -- low, medium, high, critical
    resolved BOOLEAN DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- Performance Metrics Table
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    unit TEXT,
    tags TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_dynamic_qr_user_id ON dynamic_qr_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_dynamic_qr_created_at ON dynamic_qr_codes(created_at);
CREATE INDEX IF NOT EXISTS idx_qr_scans_qr_id ON qr_scans(qr_id);
CREATE INDEX IF NOT EXISTS idx_qr_scans_time ON qr_scans(scan_time);
CREATE INDEX IF NOT EXISTS idx_qr_scans_user_agent ON qr_scans(user_agent);
CREATE INDEX IF NOT EXISTS idx_batch_user_id ON batch_qr_records(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_created_at ON batch_qr_records(created_at);
CREATE INDEX IF NOT EXISTS idx_templates_user_id ON qr_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_sessions_user_id ON payment_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp);

-- Insert Default System Configuration
INSERT OR IGNORE INTO system_config (config_key, config_value, description) VALUES
('max_qr_codes_per_user', '1000', 'Maximum QR codes per user for free tier'),
('max_batch_size', '1000', 'Maximum batch size for QR generation'),
('analytics_retention_days', '365', 'Days to retain analytics data'),
('default_qr_expiration_hours', '8760', 'Default QR expiration (1 year)'),
('api_rate_limit_per_hour', '1000', 'API rate limit per hour for users'),
('enable_cloud_storage', 'false', 'Enable cloud storage integration'),
('enable_payments', 'false', 'Enable payment processing'),
('maintenance_mode', 'false', 'Put system in maintenance mode');

-- Insert Default QR Templates
INSERT OR IGNORE INTO qr_templates (template_id, user_id, name, description, style_config, is_public) VALUES
('professional', NULL, 'Professional', 'Clean and professional look', '{"colors": {"foreground": "#1a1a1a", "background": "#ffffff"}, "frame": {"width": 15, "color": "#f0f0f0"}}', 1),
('colorful', NULL, 'Colorful', 'Bright and colorful design', '{"colors": {"foreground": "#ff6b6b", "background": "#4ecdc4"}, "pattern": {"type": "dots", "color": "#ffe66d"}}', 1),
('business', NULL, 'Business', 'Corporate style with logo support', '{"colors": {"foreground": "#2c3e50", "background": "#ecf0f1"}, "text_overlay": {"text": "Scan Me", "position": "bottom"}}', 1),
('modern', NULL, 'Modern', 'Contemporary gradient design', '{"pattern": {"type": "gradient", "start_color": "#667eea", "end_color": "#764ba2"}}', 1),
('vintage', NULL, 'Vintage', 'Retro sepia tone effect', '{"colors": {"foreground": "#8b4513", "background": "#f5deb3"}, "effects": {"types": ["vintage"]}}', 1);

-- Create Views for Common Queries
CREATE VIEW IF NOT EXISTS user_qr_stats AS
SELECT 
    u.user_id,
    u.username,
    COUNT(dqr.qr_id) as total_qr_codes,
    SUM(dqr.scan_count) as total_scans,
    MAX(dqr.last_scan) as last_scan,
    COUNT(CASE WHEN dqr.created_at > datetime('now', '-7 days') THEN 1 END) as qrs_last_7_days,
    SUM(CASE WHEN qs.scan_time > datetime('now', '-7 days') THEN 1 ELSE 0 END) as scans_last_7_days
FROM users u
LEFT JOIN dynamic_qr_codes dqr ON u.user_id = dqr.user_id
LEFT JOIN qr_scans qs ON dqr.qr_id = qs.qr_id
GROUP BY u.user_id, u.username;

CREATE VIEW IF NOT EXISTS qr_performance AS
SELECT 
    dqr.qr_id,
    dqr.user_id,
    dqr.title,
    dqr.content,
    dqr.created_at,
    dqr.scan_count,
    COUNT(qs.scan_id) as period_scans,
    MAX(qs.scan_time) as last_scan,
    COUNT(DISTINCT DATE(qs.scan_time)) as active_days
FROM dynamic_qr_codes dqr
LEFT JOIN qr_scans qs ON dqr.qr_id = qs.qr_id
GROUP BY dqr.qr_id;

CREATE VIEW IF NOT EXISTS system_health AS
SELECT 
    (SELECT COUNT(*) FROM users WHERE is_active = 1) as active_users,
    (SELECT COUNT(*) FROM dynamic_qr_codes) as total_qr_codes,
    (SELECT COUNT(*) FROM qr_scans WHERE scan_time > datetime('now', '-1 hour')) as scans_last_hour,
    (SELECT COUNT(*) FROM qr_scans WHERE scan_time > datetime('now', '-24 hours')) as scans_last_24h,
    (SELECT COUNT(*) FROM security_events WHERE timestamp > datetime('now', '-24 hours') AND resolved = 0) as unresolved_security_events;

-- Triggers for Data Integrity
CREATE TRIGGER IF NOT EXISTS update_user_login_count
    AFTER UPDATE OF last_login ON users
    WHEN NEW.last_login IS NOT NULL AND OLD.last_login IS NULL OR NEW.last_login != OLD.last_login
BEGIN
    UPDATE users SET login_count = COALESCE(login_count, 0) + 1 WHERE user_id = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS update_qr_scan_count
    AFTER INSERT ON qr_scans
BEGIN
    UPDATE dynamic_qr_codes 
    SET scan_count = scan_count + 1, last_scan = NEW.scan_time 
    WHERE qr_id = NEW.qr_id;
END;

CREATE TRIGGER IF NOT EXISTS log_qr_creation
    AFTER INSERT ON dynamic_qr_codes
BEGIN
    INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details)
    VALUES (NEW.user_id, 'create', 'qr_code', NEW.qr_id, json_object('title', NEW.title, 'content', NEW.content));
END;

CREATE TRIGGER IF NOT EXISTS log_security_event
    AFTER INSERT ON security_events
BEGIN
    UPDATE users SET is_active = 0 
    WHERE user_id = NEW.user_id 
    AND NEW.event_type = 'account_locked' 
    AND NEW.severity = 'high';
END;
