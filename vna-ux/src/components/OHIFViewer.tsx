// OHIF v3 embedded viewer implementation
interface OHIFViewerProps {
  studyInstanceUid: string
  seriesInstanceUid?: string
}

export default function OHIFViewer({ studyInstanceUid }: OHIFViewerProps) {
  return (
    <div className="w-full h-[calc(100vh-64px)] bg-black">
      <iframe
        src={`/dicom-api/ohif/viewer?StudyInstanceUIDs=${studyInstanceUid}`}
        className="w-full h-full border-0"
        title="DICOM Viewer"
      />
    </div>
  )
}
