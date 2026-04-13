# BIDS Server

### 为科研而生的数据管理平台

---

## 痛点

做医学 AI 科研，你是否遇到这些问题：

- **数据格式混乱** — DICOM、NIfTI、RAW、文档散落各处，管理靠手
- **标签打不了** — PACS 不让加自定义标签，标注靠 Excel 对着文件名找
- **Agent 对接难** — 想让 AI 自动处理数据，但没有标准化接口
- **数据集整理痛苦** — 每次发文章前花一周整理 BIDS 结构

---

## 解决方案

**BIDS Server** — 专为医学科研设计的数据管理服务

```
一个服务，解决科研数据的 存储 · 标注 · 检索 · 传输
```

### 核心能力

**🗂 全格式支持**
DICOM、NIfTI、RAW、PDF、CSV、模型权重...一个平台统一管理
不再需要多个工具分别处理不同格式

**🏷 无限标签系统**
给任何数据打任意标签，结构化标注（bbox/分割/分类）
标签自描述存储在 JSON 侧车文件中，数据走到哪标签跟到哪

**🔍 强大查询**
按患者、标签、模态、时间、元数据任意组合查询
全文搜索，毫秒级响应

**🤖 Agent 友好**
标准 REST API，curl/Python/MCP/Agent 直接对接
支持流式大文件传输、断点续传、批量操作

**📂 BIDS 原生**
数据直接按 BIDS 标准组织，一键导出数据集
再也不用手动整理 BIDS 目录结构

**🔗 VNA 集成**
与医院 PACS/HIS 无缝对接
临床数据自动进入科研平台

---

## 一句话总结

```
Orthanc 是给 PACS 用的 DICOM Server
BIDS Server 是给科研用的数据管理平台
```

| | Orthanc | BIDS Server |
|--|---------|-------------|
| 数据类型 | 仅 DICOM | DICOM + 任意格式 |
| 标签 | DICOM 固定字段 | 无限扩展 |
| 标注 | ❌ | ✅ bbox/分割/分类 |
| 目标用户 | 临床工程师 | 科研人员 + AI Agent |
| BIDS 支持 | ❌ | ✅ 原生 |

---

## 快速开始

```bash
# 一键启动
docker compose up -d

# 上传数据
curl -X POST http://localhost:8080/bidsweb/v1/store \
  -F "file=@T1w.nii.gz" \
  -F "subject_id=sub-001" \
  -F "modality=anat" \
  -F 'labels={"diagnosis": "tumor"}'

# 查询数据
curl -X POST http://localhost:8080/bidsweb/v1/query \
  -H "Content-Type: application/json" \
  -d '{"labels": {"match": ["tumor"]}}'
```

---

## 适用场景

- **医学影像 AI 研究** — 数据存储、标注、训练流水线
- **多模态数据管理** — 影像 + 临床文档 + 表格数据统一管理
- **AI Agent 工作流** — Agent 自动查询、处理、标注数据
- **数据集发布** — 按 BIDS 标准组织，直接导出共享
- **临床-科研桥梁** — 从 PACS 自动获取数据进入科研平台

---

## 技术亮点

- **BIDSweb 协议** — 对标 DICOMweb 的开放标准，REST 原生
- **自描述数据** — 标签和元数据随文件走，不依赖数据库
- **双存储架构** — DICOM 标准存储 + BIDS 科研存储
- **数据库可恢复** — 文件系统是真相，数据库可完全重建
- **无限扩展** — 模态、标签、接口均可自由扩展

---

## 开源 · 免费 · 可扩展

```
GitHub: [即将开源]
License: MIT
Docker: docker pull bids-server
Docs: http://localhost:8080/docs
```

---

**BIDS Server** — 让科研数据管理像 `curl` 一样简单。
