# Orthanc 配置参考

## 环境变量

### 基本配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__NAME` | Orthanc | 服务器名称 |
| `ORTHANC__AUTHENTICATION_ENABLED` | true | 是否启用认证 |
| `ORTHANC__VERBOSE` | false | 详细日志 |

### 存储配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__STORAGE_DIRECTORY` | /var/lib/orthanc/storage | 文件存储路径 |
| `ORTHANC__INDEX_DIRECTORY` | /var/lib/orthanc/db | 索引存储路径 |
| `ORTHANC__MAXIMUM_STORAGE_SIZE` | 0 | 最大存储(GB)，0=不限 |
| `ORTHANC__MAXIMUM_PATIENT_COUNT` | 0 | 最大患者数，0=不限 |

### PostgreSQL 数据库配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__POSTGRESQL__ENABLED` | false | 启用 PostgreSQL 插件 |
| `ORTHANC__POSTGRESQL__HOST` | localhost | PostgreSQL 主机 |
| `ORTHANC__POSTGRESQL__PORT` | 5432 | PostgreSQL 端口 |
| `ORTHANC__POSTGRESQL__DATABASE` | orthanc | 数据库名称 |
| `ORTHANC__POSTGRESQL__USERNAME` | orthanc | 用户名 |
| `ORTHANC__POSTGRESQL__PASSWORD` | - | 密码 |
| `ORTHANC__POSTGRESQL__ENABLEINDEX` | true | 使用 PostgreSQL 存储索引 |
| `ORTHANC__POSTGRESQL__ENABLESTORAGE` | false | 使用 PostgreSQL 存储 DICOM 文件 |
| `ORTHANC__POSTGRESQL__LOCK` | true | 启用数据库锁 |

### DICOM 协议

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__DICOM_AET` | ORTHANC | AE Title |
| `ORTHANC__DICOM_PORT` | 4242 | DICOM 监听端口 |
| `ORTHANC__DICOM_ALWAYS_STORE` | true | 总是存储接收的实例 |

### DICOMweb

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__DICOM_WEB__ENABLED` | false | 启用 DICOMweb |
| `ORTHANC__DICOM_WEB__ROOT` | /dicom-web/ | DICOMweb 根路径 |

### REST API

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORTHANC__REST_API_ENABLED` | true | 启用 REST API |
| `ORTHANC__EXPOSE_HTTP` | true | 暴露 HTTP |

## VNA 推荐配置

### 使用 PostgreSQL 作为后端（推荐）

```yaml
environment:
  ORTHANC__NAME: "VNA-DICOM"
  ORTHANC__AUTHENTICATION_ENABLED: "false"  # 内网使用
  ORTHANC__DICOM_AET: "VNA-ORTHANC"
  ORTHANC__DICOM_ALWAYS_STORE: "true"
  ORTHANC__REST_API_ENABLED: "true"
  ORTHANC__DICOM_WEB__ENABLED: "true"
  ORTHANC__STORAGE_DIRECTORY: "/var/lib/orthanc/storage"
  ORTHANC__MAXIMUM_STORAGE_SIZE: "0"
  ORTHANC__MAXIMUM_PATIENT_COUNT: "0"
  # PostgreSQL 配置
  ORTHANC__POSTGRESQL__ENABLED: "true"
  ORTHANC__POSTGRESQL__HOST: "postgres"
  ORTHANC__POSTGRESQL__PORT: "5432"
  ORTHANC__POSTGRESQL__DATABASE: "orthanc"
  ORTHANC__POSTGRESQL__USERNAME: "vna"
  ORTHANC__POSTGRESQL__PASSWORD: "vna"
  ORTHANC__POSTGRESQL__ENABLEINDEX: "true"
  ORTHANC__POSTGRESQL__ENABLESTORAGE: "false"
  ORTHANC__POSTGRESQL__LOCK: "false"
```

### 使用 SQLite（开发环境）

```yaml
environment:
  ORTHANC__NAME: "VNA-DICOM"
  ORTHANC__AUTHENTICATION_ENABLED: "false"
  ORTHANC__STORAGE_DIRECTORY: "/var/lib/orthanc/storage"
  ORTHANC__INDEX_DIRECTORY: "/var/lib/orthanc/db"
  ORTHANC__DICOM_AET: "VNA-ORTHANC"
  ORTHANC__REST_API_ENABLED: "true"
  ORTHANC__DICOM_WEB__ENABLED: "true"
```

## 插件配置

### OHIF Viewer

```yaml
environment:
  OHIF_PLUGIN_ENABLED: "true"
  ORTHANC__OHIF__DATASOURCE: "dicom-web"
```

### VolView

```yaml
environment:
  VOLVIEW_PLUGIN_ENABLED: "true"
```

### Orthanc Web Viewer

```yaml
environment:
  ORTHANC_WEB_VIEWER_PLUGIN_ENABLED: "true"
```

### Orthanc Explorer 2

```yaml
environment:
  ORTHANC_EXPLORER_2_ENABLED: "true"
```
