# BIDS Server - 设计文档 v1.1

> 定稿日期：2026-03-17
> 更新日期：2026-03-17
> 项目代号：BIDS Server
> 协议名称：BIDSweb (OpenAPI)
> 部署方式：Docker

---

## 1. 系统定位

BIDS Server 是 VNA 架构中 BIDS 数据库的独立服务程序，提供：
- BIDS 文件的存储、检索、查询、管理
- 标签系统的 CRUD 和搜索
- 大文件高效传输
- 可独立运行，也可接入 VNA 主数据库

对标 DICOM 数据库（DICOMweb）的功能级别。

---

## 2. 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI | 异步高性能，原生 OpenAPI 支持 |
| 数据库 | PostgreSQL 16 (生产) / SQLite (测试) | 索引、标签、元数据存储 |
| 全文搜索 | PostgreSQL 内置 (tsvector/LIKE) | 标签检索、全文搜索 |
| 文件存储 | 本地文件系统 | BIDS 目录结构 |
| ORM | SQLAlchemy 2.0 (async) | 数据库操作 |
| 文件校验 | hashlib (sha256) | 完整性校验 |
| BIDS 校验 | 自写轻量版 | 目录结构校验 |
| 容器化 | Docker + Docker Compose | 一键部署 |
| 语言 | Python 3.11+ | 全栈 |

---

## 3. 设计决策

### 3.1 数据库选型

- **生产环境**: PostgreSQL 16
- **开发/测试**: SQLite (通过 aiosqlite)
- **不使用 OpenSearch**: 初期用 PostgreSQL 全文搜索 (tsvector + LIKE) 满足需求，后期按需添加

### 3.2 JSON 字段类型

- 使用 SQLAlchemy `JSON` 类型而非 `JSONB`，确保 SQLite/PostgreSQL 兼容
- 生产环境 PostgreSQL 会自动优化 JSON 存储

### 3.3 认证授权

- 初期不做认证（内网部署场景）
- 预留接口扩展点，后期可加 API Key 或 JWT

### 3.4 任务队列

- 初期：同步处理 + 后台线程
- 后期：升级为 Celery

### 3.5 UID 命名规则

```
resource_id:  res-{uuid4前12位}    例: res-a1b2c3d4e5f6
upload_id:    upl-{uuid4前12位}    例: upl-x9y8z7w6v5u4
task_id:      tsk-{uuid4前12位}    例: tsk-m1n2o3p4q5r6
webhook_id:   whk-{uuid4前12位}    例: whk-f1e2d3c4b5a6
annotation_id:ann-{uuid4前12位}    例: ann-112233445566
subject_id:   sub-{自定义}          例: sub-001
session_id:   sub-{id}_ses-{id}    例: sub-001_ses-001
```

---

## 4. BIDS 模态定义

### 4.1 标准模态

```
模态名          目录        支持格式                      说明
─────────────  ──────────  ──────────────────────────   ──────────────
anat           anat/       .nii.gz, .nii, .json         结构 MRI
func           func/       .nii.gz, .nii, .json, .tsv   功能 MRI
dwi            dwi/        .nii.gz, .nii, .json, .bval, .bvec  弥散 MRI
fmap           fmap/       .nii.gz, .nii, .json         场图
ct             ct/         .nii.gz, .nii, .json         CT 影像
pet            pet/        .nii.gz, .nii, .json         PET 影像
microscopy     microscopy/ .ome.tiff, .tiff, .json      显微镜图像
eeg            eeg/        .edf, .bdf, .set, .json      脑电图
meg            meg/        .fif, .ds, .json             脑磁图
ieeg           ieeg/       .edf, .nwb, .json            颅内脑电
nirs           nirs/       .snirf, .json                近红外光谱
docs           docs/       .pdf, .docx, .txt, .json     文档
tables         tables/     .csv, .tsv, .xlsx, .json     表格数据
code           code/       .py, .sh, .ipynb, .json      代码/脚本
models         models/     .pth, .h5, .onnx, .json      AI 模型权重
raw            raw/        任意格式 + .json              原始非标数据
other          other/      任意格式 + .json              其他自定义
```

### 4.2 扩展方式

通过 API `POST /api/modalities` 注册新模态，或在 `config/modalities.yaml` 中定义。

---

## 5. BIDSweb 协议设计

### 5.1 与 DICOMweb 对照

```
DICOMweb              BIDSweb                    说明
─────────────────    ────────────────────────    ─────────────
POST /studies        POST /api/store      存储对象
GET  /studies/{uid}  GET  /api/objects/   检索对象
                       {resourceId}
GET  /studies?...    POST /api/query      查询对象
POST /studies/batch  POST /api/store      批量存储
                     (multipart)
GET  /wado-rs/...    GET  /api/objects/    渲染/预览
                       {resourceId}/render
-                    POST /api/tasks       异步任务
-                    GET  /api/tasks/{id}  任务状态
-                    POST /api/webhooks    事件订阅
-                    CRUD /api/labels      标签管理
-                    CRUD /api/annotations 标注管理
-                    GET  /api/subjects    患者管理
-                    GET  /api/sessions    会话管理
-                    POST /api/verify      数据校验
-                    POST /api/rebuild     数据库重建
```

### 5.2 完整 API 路径

```
BIDSweb v1 API
│
├── /api/
│   │
│   ├── store                    # 存储（对标 C-STORE / STOW-RS）
│   │   ├── POST   单文件上传
│   │   ├── POST   /init         初始化分块上传
│   │   ├── PATCH  /{uploadId}   上传分块
│   │   └── POST   /{uploadId}/complete  完成上传
│   │
│   ├── objects                  # 检索（对标 C-MOVE / WADO-RS）
│   │   ├── GET    /{resourceId}           下载文件
│   │   ├── GET    /{resourceId}/stream    流式下载（Range）
│   │   ├── GET    /{resourceId}/render    预览/渲染
│   │   ├── GET    /{resourceId}/metadata  获取侧车 JSON
│   │   ├── GET    /{resourceId}/labels    获取标签
│   │   ├── GET    /{resourceId}/annotations 获取标注
│   │   ├── GET    /{resourceId}/processing  获取处理记录
│   │   ├── GET    /{resourceId}/relationships 获取关系
│   │   ├── PUT    /{resourceId}/relationships 更新关系
│   │   ├── DELETE /{resourceId}           删除对象
│   │   └── POST   /batch-download         批量下载（zip）
│   │
│   ├── query                    # 查询（对标 C-FIND / QIDO-RS）
│   │   └── POST   组合查询
│   │
│   ├── subjects                 # 患者管理
│   │   ├── GET    列出所有患者
│   │   ├── GET    /{subjectId}            获取患者详情
│   │   ├── POST   创建患者
│   │   ├── PUT    /{subjectId}            更新患者信息
│   │   └── DELETE /{subjectId}            删除患者
│   │
│   ├── sessions                 # 会话管理
│   │   ├── GET    /?subject={id}          列出会话
│   │   ├── GET    /{sessionId}            获取会话详情
│   │   ├── POST   创建会话
│   │   ├── PUT    /{sessionId}            更新会话信息
│   │   └── DELETE /{sessionId}            删除会话
│   │
│   ├── labels                   # 标签管理
│   │   ├── GET    列出所有标签（含统计）
│   │   ├── GET    /{resourceId}           获取资源标签
│   │   ├── PUT    /{resourceId}           替换标签
│   │   └── PATCH  /{resourceId}           增量更新标签
│   │
│   ├── annotations              # 标注管理
│   │   ├── GET    列出标注
│   │   ├── GET    /{annotationId}         获取标注
│   │   ├── POST   创建标注
│   │   ├── PUT    /{annotationId}         更新标注
│   │   └── DELETE /{annotationId}         删除标注
│   │
│   ├── tasks                    # 异步任务
│   │   ├── POST   提交任务
│   │   ├── GET    /{taskId}               查询状态/结果
│   │   └── DELETE /{taskId}               取消任务
│   │
│   ├── webhooks                 # 事件订阅
│   │   ├── POST   注册 webhook
│   │   ├── GET    列出 webhook
│   │   └── DELETE /{webhookId}             删除 webhook
│   │
│   ├── modalities               # 模态管理
│   │   ├── GET    列出所有模态
│   │   └── POST   注册新模态
│   │
│   ├── verify                   # 数据校验
│   │   └── POST   校验文件完整性 / BIDS 结构
│   │
│   └── rebuild                  # 数据库重建
│       └── POST   从文件系统重建索引
```

---

## 6. 数据模型

### 6.1 PostgreSQL 表结构

```sql
-- 患者表（镜像 participants.tsv）
CREATE TABLE subjects (
    subject_id      VARCHAR(64) PRIMARY KEY,
    patient_ref     VARCHAR(128),
    hospital_ids    JSON DEFAULT '{}',
    metadata        JSON DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 会话表
CREATE TABLE sessions (
    session_id      VARCHAR(128) PRIMARY KEY,
    subject_id      VARCHAR(64) REFERENCES subjects(subject_id),
    session_label   VARCHAR(64),
    scan_date       DATE,
    metadata        JSON DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 资源表（核心表）
CREATE TABLE resources (
    resource_id     VARCHAR(64) PRIMARY KEY,
    subject_id      VARCHAR(64) REFERENCES subjects(subject_id),
    session_id      VARCHAR(128) REFERENCES sessions(session_id),
    modality        VARCHAR(32) NOT NULL,
    bids_path       TEXT NOT NULL UNIQUE,
    file_name       VARCHAR(256) NOT NULL,
    file_type       VARCHAR(32),
    file_size       BIGINT,
    content_hash    VARCHAR(128),
    source          VARCHAR(32) DEFAULT 'user_upload',
    dicom_ref       VARCHAR(256),
    metadata        JSON DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 标签表
CREATE TABLE labels (
    id              SERIAL PRIMARY KEY,
    resource_id     VARCHAR(64) REFERENCES resources(resource_id),
    level           VARCHAR(16) NOT NULL,
    target_path     TEXT,
    tag_key         VARCHAR(128) NOT NULL,
    tag_value       TEXT,
    tagged_by       VARCHAR(128),
    tagged_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 标注表
CREATE TABLE annotations (
    annotation_id   VARCHAR(64) PRIMARY KEY,
    resource_id     VARCHAR(64) REFERENCES resources(resource_id),
    ann_type        VARCHAR(32) NOT NULL,
    label           VARCHAR(128),
    data            JSON NOT NULL,
    confidence      FLOAT,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 处理记录表
CREATE TABLE processing_log (
    id              SERIAL PRIMARY KEY,
    resource_id     VARCHAR(64) REFERENCES resources(resource_id),
    pipeline        VARCHAR(128),
    input_resources JSON,
    params          JSON,
    executed_by     VARCHAR(128),
    executed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 数据关联表
CREATE TABLE relationships (
    id              SERIAL PRIMARY KEY,
    resource_id     VARCHAR(64) REFERENCES resources(resource_id) UNIQUE,
    parent_refs     JSON DEFAULT '[]',
    children_refs   JSON DEFAULT '[]',
    dicom_ref       VARCHAR(256),
    same_subject    JSON DEFAULT '[]'
);

-- 任务表
CREATE TABLE tasks (
    task_id         VARCHAR(64) PRIMARY KEY,
    action          VARCHAR(64) NOT NULL,
    resource_ids    JSON DEFAULT '[]',
    params          JSON DEFAULT '{}',
    status          VARCHAR(16) DEFAULT 'queued',
    progress        FLOAT DEFAULT 0,
    result          JSON,
    error           TEXT,
    callback_url    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Webhook 表
CREATE TABLE webhooks (
    webhook_id      VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(128),
    url             TEXT NOT NULL,
    events          JSON NOT NULL,
    secret          VARCHAR(256),
    filters         JSON DEFAULT '{}',
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 模态注册表
CREATE TABLE modalities (
    modality_id     VARCHAR(64) PRIMARY KEY,
    directory       VARCHAR(64) NOT NULL,
    description     TEXT,
    extensions      JSON NOT NULL,
    required_files  JSON DEFAULT '["json"]',
    category        VARCHAR(32) DEFAULT 'other',
    is_system       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. 文件系统结构

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
    │   ├── fmap/
    │   ├── docs/
    │   ├── tables/
    │   └── raw/
    └── ses-002/
        └── ...
```

---

## 8. 大文件传输方案

### 8.1 上传

```
Resumable Upload:

1. 初始化上传
   POST /api/store/init
   → 返回 uploadId

2. 分块上传
   PATCH /api/store/{uploadId}
   Content-Range: bytes 0-10485759/157286400
   Body: <binary chunk>

3. 完成上传
   POST /api/store/{uploadId}/complete
   → 返回 Resource 对象
```

### 8.2 下载

```
HTTP Range + Streaming:

单文件下载:
  GET /api/objects/{resourceId}/stream
  Range: bytes=0-10485759
  → 支持断点续传

批量下载:
  POST /api/objects/batch-download
  → 流式打包返回 zip
```

### 8.3 内存策略

```
小文件 (<50MB):  直接读入内存
大文件 (>=50MB): 流式读写，分块传输
```

---

## 9. 标签系统

### 9.1 存储方式

- **数据库**: labels 表存储所有标签，支持快速查询
- **JSON 侧车**: BIDS 文件同名 .json 中的 `VNA.labels` 字段
- **同步规则**: CRUD 操作同时更新数据库和 JSON 文件，JSON 是主本

### 9.2 4 层级标签

```
层级          侧车 JSON 文件                    优先级
───────────  ───────────────────────────       ─────
数据集级      dataset_description.json          最低
患者级        sub-xxx.json                      ↓
会话级        sub-xxx_ses-xxx.json              ↓
文件级        sub-xxx_ses-xxx_modality.json     最高
```

### 9.3 标签格式

```json
{
  "VNA": {
    "resourceId": "res-xxx",
    "labels": {
      "system": ["MR", "T1", "brain"],
      "custom": ["脑肿瘤", "预处理完成"],
      "diagnosis": "glioma",
      "任意键": "任意值"
    },
    "annotations": [
      {
        "id": "ann-xxx",
        "type": "bbox",
        "label": "tumor",
        "data": {"x": 120, "y": 85, "w": 45, "h": 38},
        "confidence": 0.95,
        "createdBy": "agent:seg-v2"
      }
    ],
    "processing": {
      "pipeline": "synthseg-v2",
      "input": ["res-xxx"],
      "params": {},
      "timestamp": "2026-03-17T10:00:00Z",
      "by": "agent:seg-v2"
    }
  }
}
```

---

## 10. Docker 部署架构

```
┌─────────────────────────────────────────┐
│              Docker Compose             │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │  bids-server (Python/FastAPI)    │  │
│  │  端口: 8080                      │  │
│  │  卷:   /bids_data               │  │
│  └──────────────┬───────────────────┘  │
│                 │                       │
│  ┌──────────────▼───────────────────┐  │
│  │  postgres (PostgreSQL 16)        │  │
│  │  端口: 5432                      │  │
│  │  卷:   pg_data                   │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 11. 项目结构

```
bids-server/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── README.md
├── docs/
│   └── DESIGN.md              # 本文档
├── config/
│   └── modalities.yaml        # 模态定义
├── bids_server/
│   ├── main.py                # FastAPI 入口 + 生命周期
│   ├── config.py              # 配置 (Pydantic Settings)
│   ├── api/                   # API 路由层
│   │   ├── store.py           # 存储接口
│   │   ├── objects.py         # 检索接口
│   │   ├── query.py           # 查询接口
│   │   ├── subjects.py        # 患者管理
│   │   ├── sessions.py        # 会话管理
│   │   ├── labels.py          # 标签管理
│   │   ├── annotations.py     # 标注管理
│   │   ├── tasks.py           # 任务管理
│   │   ├── webhooks.py        # 事件订阅
│   │   ├── modalities.py      # 模态管理
│   │   ├── verify.py          # 数据校验
│   │   └── rebuild.py         # 数据库重建
│   ├── models/
│   │   ├── database.py        # SQLAlchemy ORM 模型
│   │   └── schemas.py         # Pydantic 请求/响应模型
│   ├── core/
│   │   ├── storage.py         # 文件系统操作
│   │   ├── upload.py          # 分块上传管理
│   │   ├── stream.py          # 流式下载
│   │   ├── hash.py            # 文件校验
│   │   ├── bids_validator.py  # BIDS 结构校验
│   │   └── webhook_manager.py # Webhook 分发
│   ├── services/
│   │   ├── label_service.py   # 标签 CRUD + JSON 同步
│   │   ├── task_service.py    # 任务队列
│   │   └── search_service.py  # 全文搜索 (PG/SQLite)
│   └── db/
│       ├── session.py         # 连接管理
│       └── migrations/        # Alembic 迁移
└── tests/
    ├── conftest.py            # 测试配置 (SQLite)
    ├── test_core.py           # 核心模块测试
    └── test_api.py            # API 端点测试
```

---

## 12. 一致性保证机制

```
写操作：先文件，后数据库
  → 文件写成功才写数据库
  → 两者都成功才确认

定期校验（verify API）：
  → 扫描 BIDS 目录 vs 数据库记录
  → 不一致 → 报告 / 自动修复（以文件系统为准）

数据恢复（rebuild API）：
  → 数据库丢失 → 从 BIDS 文件系统 + JSON 重建索引
  → JSON 丢失 → 从数据库重建（降级方案）
```

---

## 13. VNA 集成

### 13.1 主数据库映射

主数据库维护全局资源索引表，每条记录可映射到 DICOM 或 BIDS 或两者：

```
resource_id │ source_type    │ dicom_ref      │ bids_ref
────────────┼────────────────┼────────────────┼──────────────
res-001     │ dicom_only     │ study_uid=aaa  │ NULL
res-002     │ bids_only      │ NULL           │ sub-001/ses-001/...
res-003     │ dicom_and_bids │ study_uid=bbb  │ sub-001/ses-001/...
```

### 13.2 双向同步

```
DICOM 库 ←→ 主数据库 ←→ BIDS 库

任一方变化 → 事件通知主数据库 → 更新索引
```

### 13.3 独立服务

BIDS Server 可独立运行，也可接入 VNA 主数据库作为子服务。

---

## 14. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | postgresql+asyncpg://bids:bids@postgres:5432/bidsserver | 数据库连接 |
| BIDS_ROOT | /bids_data | BIDS 数据目录 |
| UPLOAD_TEMP_DIR | /tmp/bids_uploads | 上传临时目录 |
| MAX_UPLOAD_SIZE | 10737418240 | 最大上传大小 (10GB) |
| CHUNK_SIZE | 10485760 | 分块大小 (10MB) |
| DEBUG | false | 调试模式 |
| DATABASE_ECHO | false | SQL 日志 |

---

## 15. 开发状态

- [x] 项目骨架 + FastAPI 框架
- [x] 数据库模型 (SQLAlchemy ORM, SQLite/PostgreSQL 兼容)
- [x] Pydantic 请求/响应模型
- [x] 文件存储核心 (storage, upload, stream)
- [x] BIDS 校验器
- [x] 全部 12 个 API 路由 (BIDSweb 协议)
- [x] 标签服务 (DB + JSON 侧车双向同步)
- [x] 标注服务 (bbox/point/polygon/segmentation 等)
- [x] 任务服务
- [x] 搜索服务 (PG tsvector / SQLite LIKE 自适应)
- [x] Webhook 事件分发
- [x] 分块上传 (可断点续传)
- [x] Range 流式下载
- [x] 数据校验 (verify API)
- [x] 数据库重建 (rebuild API)
- [x] 模态注册系统
- [x] Docker + Docker Compose 部署
- [x] 完整测试套件 (51 个测试全部通过)
- [x] Swagger/ReDoc 文档 (自动生成)
- [x] 设计文档

## 16. 已知限制 (后续版本)

- 无认证授权 (v1.0 不做，预留扩展点)
- 任务队列为同步+后台线程 (后续升级 Celery)
- 图像渲染仅支持原生图像格式 (NIfTI/DICOM 渲染需集成转换工具)
- 无 OpenSearch (PG 全文搜索满足当前需求)

---

_文档结束。_
