import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Download, Printer, ArrowRight } from 'lucide-react'
import { getAudit } from '../api/scan'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import AuditTimeline from '../components/domain/AuditTimeline'
import { peiColor } from '../utils/peiColor'
import { DOC_TYPES } from '../constants/docTypes'
import { maskValue } from '../utils/fieldHelpers'

export default function AuditReport() {
  const { scanId } = useParams()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!scanId) return
    setLoading(true)
    getAudit(scanId)
      .then(setReport)
      .catch(e => setError(e.message || 'failed to load report'))
      .finally(() => setLoading(false))
  }, [scanId])

  if (loading) {
    return (
      <div className="space-y-6">
        {[1,2,3].map(i => <div key={i} className="h-32 animate-shimmer rounded-[var(--r-lg)]" />)}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <p className="text-danger mb-4">{error}</p>
        <Button onClick={() => window.location.reload()}>retry</Button>
      </div>
    )
  }

  if (!report) return null

  const fields = report.fields || report.detected_fields || []
  const events = report.timeline || report.events || [
    { time: report.timestamp || report.created_at, action: 'document uploaded' },
    { time: report.timestamp || report.created_at, action: 'ocr extraction completed' },
    { time: report.timestamp || report.created_at, action: `classified as ${DOC_TYPES[report.document_type]?.label || report.document_type}` },
    { time: report.timestamp || report.created_at, action: `${fields.length} fields detected` },
    { time: report.timestamp || report.created_at, action: 'redaction applied' },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      {/* Header card */}
      <Card hover={false} className="space-y-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <p className="t-mono text-text-3 text-xs">{report.scan_id || scanId}</p>
            <h1 className="t-h2 text-text-1 mt-1">audit report</h1>
          </div>
          <div className="flex gap-2">
            <Badge variant="accent">dpdp act</Badge>
            <Badge variant="accent">gdpr art.5</Badge>
          </div>
        </div>

        <div className="flex items-center gap-6 flex-wrap text-sm">
          <span className="text-text-2">{report.timestamp || report.created_at}</span>
          <span className="text-text-2">{report.filename}</span>
          <Badge variant="accent">{DOC_TYPES[report.document_type]?.label || report.document_type}</Badge>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-text-3 text-sm">PEI</span>
          <span className="font-mono text-xl font-semibold" style={{ color: peiColor(report.pei_before || 0) }}>
            {Math.round(report.pei_before || 0)}
          </span>
          <ArrowRight size={16} className="text-text-3" />
          <span className="font-mono text-xl font-semibold" style={{ color: peiColor(report.pei_after || 0) }}>
            {Math.round(report.pei_after || 0)}
          </span>
        </div>
      </Card>

      {/* Fields table */}
      <Card hover={false}>
        <h3 className="t-h3 text-text-1 mb-4">detected fields</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left t-label text-text-3 pb-3">field</th>
                <th className="text-left t-label text-text-3 pb-3">value</th>
                <th className="text-left t-label text-text-3 pb-3">method</th>
                <th className="text-left t-label text-text-3 pb-3">decision</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f, i) => (
                <tr key={i} className="border-b border-border last:border-0">
                  <td className="py-2.5 text-sm text-text-1">{f.field_name}</td>
                  <td className="py-2.5 t-mono text-accent text-xs">{maskValue(f.field_value || f.value_preview)}</td>
                  <td className="py-2.5 text-text-3 text-xs">{f.detection_method || 'regex'}</td>
                  <td className="py-2.5">
                    <span className={`text-xs ${f.redaction_decision === 'allow' || f.required ? 'text-success' : 'text-danger'}`}>
                      {f.redaction_decision || (f.required ? 'allow' : 'redact')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Timeline */}
      <Card hover={false}>
        <h3 className="t-h3 text-text-1 mb-4">activity timeline</h3>
        <AuditTimeline events={events} />
      </Card>

      {/* Download row */}
      <div className="flex gap-3">
        <Button variant="ghost" onClick={() => {
          const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url; a.download = `audit-${scanId}.json`; a.click()
          URL.revokeObjectURL(url)
        }}>
          <Download size={14} /> download json
        </Button>
        <Button variant="ghost" onClick={() => window.print()}>
          <Printer size={14} /> print report
        </Button>
      </div>
    </motion.div>
  )
}
