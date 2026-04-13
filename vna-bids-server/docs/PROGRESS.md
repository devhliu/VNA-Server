# BIDS Server - 开发进度

> 更新日期：2026-03-17

---

## 总体进度：Phase 1-5 完成 ✅

```
Phase 1: 核心骨架      ████████████████████ 100%
Phase 2: BIDSweb 协议  ████████████████████ 100%
Phase 3: 大文件传输     ████████████████████ 100%
Phase 4: 高级功能      ████████████████████ 100%
Phase 5: 集成与部署     ████████████████████ 100%
```

---

## 已完成功能

### 数据管理
| 功能 | 状态 | 说明 |
|------|------|------|
| 患者管理 (CRUD) | ✅ | sub-xxx 标识，支持多医院 ID 映射 |
| 会话管理 (CRUD) | ✅ | ses-xxx 层级，关联患者 |
| 资源存储 | ✅ | 支持所有 BIDS 模态 |
| 文件上传 | ✅ | 单文件 + 批量 + 分块续传 |
| 文件下载 | ✅ | 普通 + Range 流式 + 批量 zip |
| 数据查询 | ✅ | 多条件组合查询 |
| 数据校验 | ✅ | 文件完整性 + BIDS 结构 |
| 数据库重建 | ✅ | 从文件系统恢复索引 |

### 标签与标注
| 功能 | 状态 | 说明 |
|------|------|------|
| 标签 CRUD | ✅ | set/patch/get，无限扩展 |
| JSON 侧车同步 | ✅ | DB ↔ BIDS JSON 双向同步 |
| 结构化标注 | ✅ | bbox/point/polygon/segmentation/text/classification |
| 全文搜索 | ✅ | PG tsvector / SQLite LIKE |

### 系统功能
| 功能 | 状态 | 说明 |
|------|------|------|
| 模态注册 | ✅ | 17 种预设 + 自定义扩展 |
| 异步任务 | ✅ | 队列管理 + 状态追踪 |
| Webhook | ✅ | 事件订阅 + 签名验证 |
| BIDS 校验 | ✅ | 路径/文件名/模态验证 |
| 流式传输 | ✅ | 分块上传 + Range 下载 |

### 部署与测试
| 功能 | 状态 | 说明 |
|------|------|------|
| Docker 部署 | ✅ | docker-compose 一键启动 |
| API 文档 | ✅ | Swagger + ReDoc 自动生成 |
| 测试套件 | ✅ | 51 个测试全部通过 |
| 文档 | ✅ | 设计文档 + 使用指南 |

---

## 测试覆盖

```
tests/test_core.py    13 tests  ✅ (0 warnings)
  - BIDS 校验器        8 tests
  - 流式 Range 解析    5 tests

tests/test_api.py     38 tests  ✅ (0 warnings)
  - 健康检查           2 tests
  - 患者管理           7 tests
  - 会话管理           2 tests
  - 文件存储           3 tests
  - 文件检索           5 tests
  - 标签管理           4 tests
  - 标注管理           2 tests
  - 数据查询           3 tests
  - 模态管理           2 tests
  - 数据校验           1 test
  - 数据库重建         1 test
  - 任务管理           3 tests
  - Webhook           3 tests

总计：51 tests passed, 0 warnings
测试命令：pytest tests/ -v
```

---

## 代码质量

- ✅ 所有 datetime.utcnow() 已替换为 datetime.now(timezone.utc)
- ✅ 无 DeprecationWarning
- ✅ 无 dead code
- ✅ 无未使用导入
- ✅ 所有 Python 文件语法正确

---

## 技术决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据库 | PostgreSQL (生产) / SQLite (测试) | JSON 兼容，全文搜索 |
| ORM | SQLAlchemy 2.0 async | 异步支持，双数据库兼容 |
| JSON 类型 | JSON (非 JSONB) | SQLite 兼容 |
| 认证 | 暂无 | 内网部署，v1.1 加 |
| 任务队列 | 同步+线程 | 简化部署，v1.1 加 Celery |
| 搜索 | PG 全文搜索 | 够用，暂不需要 OpenSearch |
| Session 管理 | 端点自主管理 | 避免事务冲突 |
| 时间处理 | datetime.now(timezone.utc) | Python 3.12+ 兼容 |

---

## 已知问题

无阻塞性问题。

---

_下次更新：v1.1 开发启动时_
