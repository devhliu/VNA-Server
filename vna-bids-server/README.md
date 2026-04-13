# BIDS Server

BIDS Server 是一个基于 **BIDSweb** 协议的数据管理服务，用于存储、检索、查询和管理 BIDS 格式的科研数据。

## 特性

- **BIDSweb API** — 完整的 RESTful 接口（对标 DICOMweb）
- **多模态支持** — 影像、文档、表格、代码、模型等各类数据
- **标签系统** — 无限扩展的键值对标签，与 JSON 侧车文件双向同步
- **大文件传输** — 分块上传（可断点续传）+ Range 流式下载
- **数据校验** — 完整性校验、BIDS 结构验证
- **数据库恢复** — 从文件系统完全重建索引
- **事件通知** — Webhook 订阅资源变更事件
- **PostgreSQL 全文搜索** — 标签和元数据全文检索

## 快速开始

### Docker 部署（推荐）

```bash
# 启动服务
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f bids-server
```

服务启动后访问：
- **API**: http://localhost:8080/bidsweb/v1/
- **Swagger 文档**: http://localhost:8080/docs
- **ReDoc 文档**: http://localhost:8080/redoc

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 PostgreSQL (需要本地运行或修改 DATABASE_URL)
# 修改 config/settings.env 中的 DATABASE_URL

# 启动服务
uvicorn bids_server.main:app --reload --port 8080
```

## API 概览

```
BIDSweb v1 API
│
├── /bidsweb/v1/store          # 文件存储 (上传)
│   ├── POST   /init           # 初始化分块上传
│   ├── PATCH  /{uploadId}     # 上传分块
│   ├── POST   /{uploadId}/complete  # 完成上传
│   └── POST   /               # 直接上传单文件
│
├── /bidsweb/v1/objects        # 文件检索 (下载)
│   ├── GET    /{id}           # 下载文件
│   ├── GET    /{id}/stream    # 流式下载 (支持 Range)
│   ├── GET    /{id}/metadata  # 获取侧车 JSON
│   ├── GET    /{id}/render    # 渲染预览
│   ├── GET    /{id}/labels    # 获取标签
│   ├── GET    /{id}/annotations  # 获取标注
│   ├── GET    /{id}/processing   # 获取处理记录
│   ├── DELETE /{id}           # 删除文件
│   └── POST   /batch-download # 批量下载 (zip)
│
├── /bidsweb/v1/query          # 数据查询
│   └── POST   /               # 组合查询
│
├── /bidsweb/v1/subjects       # 患者管理
│   ├── GET    /               # 列出患者
│   ├── POST   /               # 创建患者
│   ├── GET    /{id}           # 获取患者
│   ├── PUT    /{id}           # 更新患者
│   └── DELETE /{id}           # 删除患者
│
├── /bidsweb/v1/sessions       # 会话管理
│   ├── GET    /               # 列出会话
│   ├── POST   /               # 创建会话
│   ├── GET    /{id}           # 获取会话
│   └── DELETE /{id}           # 删除会话
│
├── /bidsweb/v1/labels         # 标签管理
│   ├── GET    /               # 列出所有标签
│   ├── GET    /{resourceId}   # 获取资源标签
│   ├── PUT    /{resourceId}   # 替换标签
│   └── PATCH  /{resourceId}   # 增量更新标签
│
├── /bidsweb/v1/annotations    # 标注管理
│   ├── GET    /               # 列出标注
│   ├── POST   /               # 创建标注
│   ├── PUT    /{id}           # 更新标注
│   └── DELETE /{id}           # 删除标注
│
├── /bidsweb/v1/tasks          # 异步任务
│   ├── GET    /               # 列出任务
│   ├── POST   /               # 提交任务
│   ├── GET    /{id}           # 查询状态
│   └── DELETE /{id}           # 取消任务
│
├── /bidsweb/v1/webhooks       # 事件订阅
│   ├── GET    /               # 列出 webhooks
│   ├── POST   /               # 注册 webhook
│   └── DELETE /{id}           # 删除 webhook
│
├── /bidsweb/v1/modalities     # 模态管理
│   ├── GET    /               # 列出模态
│   └── POST   /               # 注册新模态
│
├── /bidsweb/v1/verify         # 数据校验
│   └── POST   /               # 校验完整性
│
└── /bidsweb/v1/rebuild        # 数据库重建
    └── POST   /               # 从文件系统重建
```

## 使用示例

### 上传文件

```bash
# 直接上传
curl -X POST http://localhost:8080/bidsweb/v1/store \
  -F "file=@sub-001_ses-001_T1w.nii.gz" \
  -F "subject_id=sub-001" \
  -F "session_id=sub-001_ses-001" \
  -F "modality=anat" \
  -F 'labels={"diagnosis": "tumor", "qc": "pass"}'
```

### 查询数据

```bash
curl -X POST http://localhost:8080/bidsweb/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "sub-001",
    "modality": ["anat"],
    "labels": {"match": ["tumor"]}
  }'
```

### 下载文件

```bash
# 普通下载
curl http://localhost:8080/bidsweb/v1/objects/res-xxxxx -o output.nii.gz

# 流式下载（大文件）
curl http://localhost:8080/bidsweb/v1/objects/res-xxxxx/stream \
  -H "Range: bytes=0-10485759" -o partial.bin
```

### 打标签

```bash
curl -X PUT http://localhost:8080/bidsweb/v1/labels/res-xxxxx \
  -H "Content-Type: application/json" \
  -d '{"labels": {"diagnosis": "glioma", "grade": "3", "reviewed": "true"}}'
```

### 创建标注

```bash
curl -X POST http://localhost:8080/bidsweb/v1/annotations \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": "res-xxxxx",
    "ann_type": "bbox",
    "label": "tumor",
    "data": {"x": 120, "y": 85, "w": 45, "h": 38},
    "confidence": 0.95,
    "created_by": "doctor:alice"
  }'
```

### 数据库重建

```bash
curl -X POST http://localhost:8080/bidsweb/v1/rebuild \
  -H "Content-Type: application/json" \
  -d '{"target": "all", "clear_existing": false}'
```

## BIDS 目录结构

```
/bids_data/
└── sub-001/
    ├── sub-001.json                    # 患者级标签
    ├── ses-001/
    │   ├── sub-001_ses-001.json        # 会话级标签
    │   ├── anat/
    │   │   ├── sub-001_ses-001_T1w.nii.gz
    │   │   ├── sub-001_ses-001_T1w.json          # 侧车（标签+元数据）
    │   │   ├── sub-001_ses-001_T1w_dseg.nii.gz   # 处理结果
    │   │   └── sub-001_ses-001_T1w_dseg.json
    │   ├── func/
    │   ├── dwi/
    │   ├── docs/
    │   ├── tables/
    │   └── raw/
    └── ses-002/
        └── ...
```

## 支持的模态

| 模态 | 目录 | 说明 |
|------|------|------|
| anat | anat/ | 结构 MRI |
| func | func/ | 功能 MRI |
| dwi | dwi/ | 弥散 MRI |
| fmap | fmap/ | 场图 |
| ct | ct/ | CT |
| pet | pet/ | PET |
| microscopy | microscopy/ | 显微镜 |
| eeg | eeg/ | 脑电图 |
| meg | meg/ | 脑磁图 |
| docs | docs/ | 文档 |
| tables | tables/ | 表格 |
| code | code/ | 代码 |
| models | models/ | 模型权重 |
| raw | raw/ | 原始数据 |
| other | other/ | 其他自定义 |

可通过 API 或 `config/modalities.yaml` 注册新模态。

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio aiosqlite httpx

# 运行测试
pytest tests/ -v
```

## 项目结构

```
bids-server/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── config/
│   └── modalities.yaml
├── bids_server/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── api/                 # API 路由
│   │   ├── store.py         # 存储
│   │   ├── objects.py       # 检索
│   │   ├── query.py         # 查询
│   │   ├── subjects.py      # 患者
│   │   ├── sessions.py      # 会话
│   │   ├── labels.py        # 标签
│   │   ├── annotations.py   # 标注
│   │   ├── tasks.py         # 任务
│   │   ├── webhooks.py      # Webhook
│   │   ├── modalities.py    # 模态
│   │   ├── verify.py        # 校验
│   │   └── rebuild.py       # 重建
│   ├── models/              # 数据模型
│   │   ├── database.py      # SQLAlchemy
│   │   └── schemas.py       # Pydantic
│   ├── core/                # 核心逻辑
│   │   ├── storage.py       # 文件操作
│   │   ├── upload.py        # 分块上传
│   │   ├── stream.py        # 流式传输
│   │   ├── hash.py          # 文件校验
│   │   ├── bids_validator.py
│   │   └── webhook_manager.py
│   ├── services/            # 业务服务
│   │   ├── label_service.py
│   │   ├── task_service.py
│   │   └── search_service.py
│   └── db/                  # 数据库
│       ├── session.py
│       └── migrations/
└── tests/                   # 测试
    ├── conftest.py
    ├── test_core.py
    └── test_api.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | postgresql+asyncpg://bids:bids@localhost:5432/bidsserver | 数据库连接 |
| BIDS_ROOT | /bids_data | BIDS 数据目录 |
| UPLOAD_TEMP_DIR | /tmp/bids_uploads | 上传临时目录 |
| MAX_UPLOAD_SIZE | 10737418240 | 最大上传大小 (10GB) |
| CHUNK_SIZE | 10485760 | 分块大小 (10MB) |
| DEBUG | false | 调试模式 |

## License

MIT
