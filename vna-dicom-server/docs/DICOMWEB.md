# DICOMweb API 端点

Orthanc 的 DICOMweb 实现，用于 RESTful 影像访问。

## 基础 URL

```
http://localhost:8042/dicom-web/
```

## QIDO-RS (查询)

查询研究/序列/实例。

```
# 查询所有研究
GET /dicom-web/studies

# 按患者 ID 查询
GET /dicom-web/studies?PatientID=P001

# 按日期查询
GET /dicom-web/studies?StudyDate=20240101-20241231

# 按模态查询
GET /dicom-web/studies?ModalitiesInStudy=CT

# 查询某研究的序列
GET /dicom-web/studies/{studyUid}/series

# 查询某序列的实例
GET /dicom-web/studies/{studyUid}/series/{seriesUid}/instances
```

## WADO-RS (检索)

检索影像数据。

```
# 检索完整研究（DICOM 格式）
GET /dicom-web/studies/{studyUid}

# 检索序列
GET /dicom-web/studies/{studyUid}/series/{seriesUid}

# 检索单个实例
GET /dicom-web/studies/{studyUid}/series/{seriesUid}/instances/{instanceUid}

# 检索实例的元数据
GET /dicom-web/studies/{studyUid}/series/{seriesUid}/instances/{instanceUid}/metadata

# 渲染为图片（JPEG/PNG）
GET /dicom-web/studies/{studyUid}/series/{seriesUid}/instances/{instanceUid}/render
  ?viewport=512,512
```

## STOW-RS (存储)

上传 DICOM 数据。

```
# 上传单个或多个 DICOM 实例
POST /dicom-web/studies
Content-Type: multipart/related; type="application/dicom"

<binary DICOM data>
```

## 与 VNA SDK 集成

```python
from dicom_sdk import DicomClient

client = DicomClient("http://localhost:8042")

# 等价于 QIDO-RS
studies = client.query(patient_id="P001", modality="MR")

# 等价于 WADO-RS
client.retrieve("1.2.3.4.5", output_dir="./downloads/")

# 等价于 STOW-RS
client.store("scan.dcm")
```

## 响应格式

所有响应为 JSON（查询）或二进制 DICOM（检索）。

### 查询响应示例

```json
[
  {
    "StudyInstanceUID": "1.2.3.4.5",
    "PatientID": "P001",
    "PatientName": "Doe^John",
    "StudyDate": "20240315",
    "Modality": "MR",
    "StudyDescription": "Brain MRI"
  }
]
```
