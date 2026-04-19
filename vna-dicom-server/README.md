# VNA DICOM Server (Orthanc)

VNA 项目的临床 DICOM 数据管理组件，使用 [Orthanc](https://www.orthanc-server.com/) 开源 DICOM 服务器。

## 概述

DICOM Server 负责处理所有符合 DICOM 标准的临床影像数据，是 VNA 与医院 PACS/HIS 系统对接的入口。

## 技术选型

- **软件**: Orthanc 26.1.0
- **基础镜像**: `orthancteam/orthanc:26.1.0`
- **协议**: DICOM, DICOMweb, REST API

## 已启用插件

| 插件 | 环境变量 | 说明 |
|------|----------|------|
| DICOMweb | `DICOM_WEB_PLUGIN_ENABLED` | RESTful DICOM 查询/存储/检索 |
| OHIF | `OHIF_PLUGIN_ENABLED` | Web 医学影像查看器（OHIF 平台） |
| VolView | `VOLVIEW_PLUGIN_ENABLED` | 3D 体数据查看器（VoxViewer 升级版） |
| OrthancWebViewer | `ORTHANC_WEB_VIEWER_PLUGIN_ENABLED` | 传统 Web 查看器 |
| OrthancExplorer2 | `ORTHANC_EXPLORER_2_ENABLED` | Orthanc 管理界面（默认启用） |
| PostgreSQL Index | `ORTHANC__POSTGRESQL__ENABLEINDEX=true` | PostgreSQL 索引（替代 SQLite） |

## 端口

| 端口 | 协议 | 用途 |
|------|------|------|
| 4242 | DICOM | C-STORE/C-FIND/C-MOVE/C-ECHO |
| 8042 | HTTP | Web UI + REST API + DICOMweb + OHIF |

## 已启用功能

### DICOM 协议
- **C-STORE** — 接收影像
- **C-FIND** — 查询影像
- **C-MOVE** — 检索影像
- **C-ECHO** — 连通性测试

### DICOMweb
- **STOW-RS** — RESTful 存储
- **QIDO-RS** — RESTful 查询
- **WADO-RS** — RESTful 检索

### Web 查看器

#### OHIF Viewer
访问路径: `http://localhost:8042/ohif/`

OHIF (Open Health Imaging Foundation) 是一个可扩展的 Web 医学影像查看平台。配置使用 DICOMweb 作为数据源。

#### VolView Viewer
访问路径: `http://localhost:8042/volview/index.html`

VolView 是一款现代化的 3D 体数据查看器，适合交互式医学影像分析。

#### Orthanc Explorer 2
访问路径: `http://localhost:8042/ui/app/`

Orthanc 内置的 Web 管理界面，可进行患者/研究/序列管理。

#### Orthanc Web Viewer
访问路径: `http://localhost:8042/web-viewer/app/viewer.html`

传统 2D 医学影像查看器。

## PostgreSQL 索引配置

Orthanc 使用 PostgreSQL 作为索引数据库（DICOM 文件仍存储在本地文件系统）：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| EnableIndex | true | 启用 PostgreSQL 索引 |
| EnableStorage | false | DICOM 文件存储在文件系统 |
| Host | postgres | PostgreSQL 服务地址 |
| Port | 5432 | PostgreSQL 端口 |
| Database | orthanc | 数据库名 |
| Username | `${POSTGRES_USER}` (see .env) | 数据库用户 |
| Lock | false | 支持多 Orthanc 实例 |
| EnableSsl | false | 不使用 SSL |

这种配置方案的优点：
- PostgreSQL 索引提供高效的查询性能
- DICOM 文件存储在文件系统，适合大文件和高吞吐量
- 可以利用 NAS 等外部存储实现灾难恢复

## Docker Compose 配置

```yaml
dicom-server:
  build: ./vna-dicom-server
  image: vna-dicom-server:local
  ports:
    - "4242:4242"
    - "8042:8042"
  environment:
    ORTHANC__NAME: "VNA DICOM Server"
    ORTHANC__DICOM_AET: "VNA-ORTHANC"
    ORTHANC__DICOM_WEB__ENABLED: "true"
    ORTHANC__REST_API_ENABLED: "true"
    ORTHANC__AUTHENTICATION_ENABLED: "true"
    ORTHANC__REMOTE_ACCESS_ALLOWED: "true"
    ORTHANC__STABLE_AGE: "60"
    ORTHANC__STORAGE_DIRECTORY: "/var/lib/orthanc/storage"
    ORTHANC__POSTGRESQL__ENABLEINDEX: "true"
    ORTHANC__POSTGRESQL__ENABLESTORAGE: "false"
    ORTHANC__POSTGRESQL__HOST: "postgres"
    ORTHANC__POSTGRESQL__PORT: "5432"
    ORTHANC__POSTGRESQL__DATABASE: "orthanc"
    ORTHANC__POSTGRESQL__USERNAME: "${POSTGRES_USER}"
    ORTHANC__POSTGRESQL__PASSWORD: "${POSTGRES_PASSWORD}"
    ORTHANC__POSTGRESQL__LOCK: "false"
    OHIF_PLUGIN_ENABLED: "true"
    ORTHANC__OHIF__DATASOURCE: "dicom-web"
    VOLVIEW_PLUGIN_ENABLED: "true"
    ORTHANC_WEB_VIEWER_PLUGIN_ENABLED: "true"
    ORTHANC_EXPLORER_2_ENABLED: "true"
  volumes:
    - orthanc_data:/var/lib/orthanc/db
    - orthanc_storage:/var/lib/orthanc/storage
  depends_on:
    postgres:
      condition: service_healthy
```

## 单独运行

```bash
docker compose up -d --build
```

默认凭据 (通过 .env 文件配置):

- 用户名: `${DICOM_SERVER_USER}`
- 密码: `${DICOM_SERVER_PASSWORD}`

## 与 VNA 集成

```
PACS ──DICOM──→ Orthanc ──REST/Sync Event──→ VNA Main DB
                    │
                    ├── 存储 DICOM 文件
                    ├── PostgreSQL 索引查询
                    ├── 触发同步事件到主数据库
                    └── 提供 OHIF/VolView 查看
```

## 查看器访问指南

1. **OHIF Viewer** (推荐)
   - URL: `http://localhost:8042/ohif/`
   - 特点：现代界面，支持多种阅片工具

2. **VolView Viewer**
   - URL: `http://localhost:8042/volview/index.html`
   - 特点：3D 体渲染，适合高级可视化

3. **Orthanc Explorer 2** (管理界面)
   - URL: `http://localhost:8042/ui/app/`
   - 特点：完整的 Orthanc 管理功能

4. **Orthanc Web Viewer**
   - URL: `http://localhost:8042/web-viewer/app/viewer.html`
   - 特点：传统 2D 阅片

## 客户端 SDK

使用 VNA DICOM SDK 与 Orthanc 交互：

```python
from dicom_sdk import DicomClient

client = DicomClient("http://localhost:8042")
client.store("scan.dcm")
studies = client.query(patient_id="P001")
```

## 相关链接

- [Orthanc 官方文档](https://orthanc-server.com/)
- [Orthanc Book (官方手册)](https://orthanc.uclouvain.be/book/index.html)
- [OHIF Viewer 文档](https://docs.ohif.org/)
- [VolView 文档](https://volview.netlify.app/)
- [DICOM 标准](https://www.dicomstandard.org/)
- [DICOMweb 规范](https://www.dicomstandard.org/dicomweb/)
