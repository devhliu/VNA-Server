# BIDS Server - 开发计划

> 版本：1.0
> 更新日期：2026-03-17

---

## Phase 1: 核心骨架 ✅

- [x] FastAPI 项目搭建
- [x] PostgreSQL 表设计（SQLAlchemy ORM）
- [x] 基本 CRUD（subjects, sessions, resources）
- [x] 单文件上传/下载
- [x] Pydantic 请求/响应模型

## Phase 2: BIDSweb 协议 ✅

- [x] 完整 API 路由（12 个模块）
- [x] 查询引擎（多条件组合查询）
- [x] 标签 CRUD + JSON 侧车同步
- [x] 标注管理（bbox/point/polygon/segmentation 等）
- [x] 模态注册系统

## Phase 3: 大文件传输 ✅

- [x] 分块上传（resumable upload）
- [x] 流式下载（HTTP Range 支持）
- [x] 批量打包下载（zip）

## Phase 4: 高级功能 ✅

- [x] 任务队列（同步 + 后台线程）
- [x] Webhook 事件订阅
- [x] 数据校验（verify API）
- [x] 数据库重建（rebuild API）
- [x] 全文搜索（PG tsvector / SQLite LIKE）

## Phase 5: 集成与部署 ✅

- [x] Docker + Docker Compose
- [x] 完整测试套件（51 个测试）
- [x] README 使用文档
- [x] 设计文档（DESIGN.md）

---

## 后续版本（v1.1+）

- [ ] 认证授权（API Key / JWT）
- [ ] Celery 任务队列替换
- [ ] OpenSearch 集成（大数据量搜索）
- [ ] NIfTI/DICOM 图像渲染预览
- [ ] Python SDK 自动生成
- [ ] MCP Server 封装
- [ ] 性能优化（连接池、缓存）
