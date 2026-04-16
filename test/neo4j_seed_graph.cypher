// =============================================================================
// Neo4j 关系网络种子：User -[:TRANSFER]-> User（资金/关联转移）
// 用法见同目录 load_graph_seed.sh
//
// 默认 tenant_id = 1，对应 PostgreSQL users 表里 id=1 的用户（常见为 admin）。
// 若你登录用户 id 不是 1：在编辑器中全局替换 tenant_id: 1 为你的 users.id。
// =============================================================================

// 仅清理由本脚本约定名称的节点（避免误删全库时请先备份）
MATCH (u:User)
WHERE u.tenant_id = 1 AND u.name IN ['张伟','李娜','王强','刘洋','陈静','杨磊','赵敏','黄涛','周杰','吴军']
DETACH DELETE u;

// 人物节点（与 CSV mock_graph_flow.csv 中 name 列一致）
UNWIND [
  '张伟','李娜','王强','刘洋','陈静','杨磊','赵敏','黄涛','周杰','吴军'
] AS person
MERGE (u:User {name: person, tenant_id: 1});

// 转账/关联边：链式 + 横向勾结，便于出度与可视化
MATCH (a:User {name:'张伟', tenant_id:1}), (b:User {name:'李娜', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'李娜', tenant_id:1}), (b:User {name:'王强', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'王强', tenant_id:1}), (b:User {name:'刘洋', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'刘洋', tenant_id:1}), (b:User {name:'陈静', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'陈静', tenant_id:1}), (b:User {name:'杨磊', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'杨磊', tenant_id:1}), (b:User {name:'赵敏', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'赵敏', tenant_id:1}), (b:User {name:'黄涛', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'黄涛', tenant_id:1}), (b:User {name:'周杰', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'周杰', tenant_id:1}), (b:User {name:'吴军', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);

MATCH (a:User {name:'张伟', tenant_id:1}), (b:User {name:'王强', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'李娜', tenant_id:1}), (b:User {name:'刘洋', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'王强', tenant_id:1}), (b:User {name:'杨磊', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'陈静', tenant_id:1}), (b:User {name:'赵敏', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);
MATCH (a:User {name:'吴军', tenant_id:1}), (b:User {name:'张伟', tenant_id:1}) MERGE (a)-[:TRANSFER]->(b);

RETURN 'seed_ok' AS status;
