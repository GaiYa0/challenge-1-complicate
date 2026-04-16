图相关模拟数据说明（本目录）
================================

一、做什么用
-----------
1) neo4j_seed_graph.cypher + load_graph_seed.sh
   - 在 Neo4j 中写入 User 节点（带 tenant_id）与 TRANSFER 有向边。
   - 数据分析页「Neo4j」关系图（G6）、图管理里的关系/出度列表会用到。
   - 异步任务「图分析 graph」会把 Neo4j 出度与 CSV 中按 name 汇总的 amount 结合算风险。

2) mock_graph_flow.csv
   - 可上传「文件中心」的流水表；必须含列 name、amount（与后端 analyze 一致）。
   - 人物姓名与 neo4j_seed_graph.cypher 中节点 name 一致，且默认 tenant_id=1 与首个用户（常为 admin）对齐。

二、如何导入 Neo4j 种子
-----------------------
  ./test/load_graph_seed.sh

  或手动：
  docker exec -i challenge-neo4j cypher-shell -u neo4j -p <密码> < test/neo4j_seed_graph.cypher

三、若图分析里 Neo4j 出度始终为 0
---------------------------------
  检查 PostgreSQL 里当前登录用户的 id 是否为 1；若不是，编辑 neo4j_seed_graph.cypher，
  将全部 tenant_id: 1 改为你的 users.id 后重新执行 load_graph_seed.sh。

四、与 mock_bank_flow_submit.csv 的区别
--------------------------------------
  mock_graph_flow.csv 人物与 Neo4j 种子严格对齐，专用于「出图 + 图分析」联调；
  mock_bank_flow_submit.csv 为更泛化的银行流水样例，人物更多、不保证与库中图节点一致。
