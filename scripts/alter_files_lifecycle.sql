-- 已有 PostgreSQL 库升级：为 files 表增加生命周期与成本相关列。
-- 执行前请备份；列默认值与 ORM 保持一致。

ALTER TABLE files ADD COLUMN IF NOT EXISTS lifecycle_tier VARCHAR(16) NOT NULL DEFAULT 'hot';
ALTER TABLE files ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMP NULL;
ALTER TABLE files ADD COLUMN IF NOT EXISTS access_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE files ADD COLUMN IF NOT EXISTS warm_month_key VARCHAR(7) NULL;
ALTER TABLE files ADD COLUMN IF NOT EXISTS cold_bucket_name VARCHAR(128) NULL;
ALTER TABLE files ADD COLUMN IF NOT EXISTS cold_object_name VARCHAR(1024) NULL;
ALTER TABLE files ADD COLUMN IF NOT EXISTS archive_format VARCHAR(32) NOT NULL DEFAULT 'none';

CREATE INDEX IF NOT EXISTS ix_files_lifecycle_created ON files (lifecycle_tier, created_at);
CREATE INDEX IF NOT EXISTS ix_files_warm_month_key ON files (warm_month_key);
