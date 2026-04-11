-- 示例：按 warm_month_key（YYYY-MM）对 files 做范围分区（PostgreSQL 10+）。
-- 生产需停机迁移或双写；此处仅作设计参考，勿直接在生产未评估时执行。

-- 1) 新建分区父表（示意，实际应从空表开始规划）
-- CREATE TABLE files_p (LIKE files INCLUDING DEFAULTS INCLUDING INDEXES) PARTITION BY LIST (warm_month_key);

-- 2) 为每个月增加分区
-- CREATE TABLE files_p_2026_04 PARTITION OF files_p FOR VALUES IN ('2026-04');

-- 3) 将历史数据迁入分区表后切换视图或表名。

COMMENT ON TABLE files IS '建议：新系统直接用分区表；存量表可用 ALTER 脚本加列后渐进迁移。';
