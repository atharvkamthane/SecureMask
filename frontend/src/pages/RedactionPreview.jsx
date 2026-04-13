import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Download, FileText, Loader2, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'
import { useScan } from '../hooks/useScan'
import { useRedaction } from '../hooks/useRedaction'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { peiColor } from '../utils/peiColor'

export default function RedactionPreview() {
  const { scan, decisions, updateDecision } = useScan()
  const { applyRedaction, loading } = useRedaction()
  const navigate = useNavigate()

  if (!scan) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <p className="text-text-2 mb-4">no scan data available</p>
        <Button onClick={() => navigate('/upload')}>upload a document</Button>
      </div>
    )
  }

  const fields = scan.detected_fields || []
  const peiAfter = useMemo(() => {
    return Math.min(fields.reduce((acc, f) => {
      const dec = decisions[f.field_name] || 'redact'
      if (dec === 'allow') return acc + (f.required ? f.sensitivity_weight * 2 : f.sensitivity_weight * 10)
      return acc + (f.required ? f.sensitivity_weight * 2 : 0)
    }, 0), 100)
  }, [fields, decisions])

  const buttons = [
    { key: 'mask', label: 'Mask', color: 'var(--warning)' },
    { key: 'redact', label: 'Redact', color: 'var(--danger)' },
    { key: 'allow', label: 'Allow', color: 'var(--success)' },
  ]

  const handleApplyRedaction = async () => {
    try {
      const result = await applyRedaction(decisions)
      if (result?.redacted_image_url) {
        toast.success('redacted document generated')
      }
    } catch {}
  }

  const handleDownload = () => {
    if (scan.redacted_image_url) {
      const link = document.createElement('a')
      link.href = scan.redacted_image_url
      link.download = `redacted_${scan.filename || 'document'}.png`
      link.click()
      toast.success('downloading redacted document')
    } else {
      toast.error('generate redaction first')
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <h1 className="t-h2 text-text-1">redaction preview</h1>

      {/* Side by side preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Original */}
        <div className="space-y-2">
          <Badge variant="high">original</Badge>
          <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
            {(scan.original_file_url || scan.processable_image_url)
              ? <img src={scan.original_file_url || scan.processable_image_url} alt="Original document" className="w-full h-auto block" />
              : <div className="h-64 flex items-center justify-center text-text-3 text-sm">no preview available</div>
            }
          </div>
        </div>

        {/* Protected */}
        <div className="space-y-2">
          <Badge variant="low">protected</Badge>
          <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
            {scan.redacted_image_url
              ? <img src={scan.redacted_image_url} alt="Redacted document" className="w-full h-auto block" />
              : <div className="h-64 flex flex-col items-center justify-center text-text-3 text-sm gap-3">
                  <p>click "generate redaction" to see the protected version</p>
                  <Button size="sm" onClick={handleApplyRedaction} disabled={loading}>
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    generate redaction
                  </Button>
                </div>
            }
          </div>
        </div>
      </div>

      {/* Field decision controls */}
      <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-bg-surface-2">
          <span className="t-label text-text-3">field decisions</span>
        </div>
        <div className="divide-y divide-border">
          {fields.map((f, i) => (
            <div key={i} className="px-4 py-3 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-sm text-text-1 truncate font-medium">{f.field_name}</span>
                <span className="text-text-3 text-xs truncate max-w-[180px]" title={f.field_value}>
                  {f.field_value || '—'}
                </span>
                {f.required
                  ? <span className="text-success text-[10px] shrink-0 font-medium">required</span>
                  : <span className="text-danger text-[10px] shrink-0 font-medium">excess</span>
                }
              </div>
              <div className="flex gap-1.5 shrink-0">
                {buttons.map(b => {
                  const active = decisions[f.field_name] === b.key
                  const isDisabled = f.always_redact && b.key !== 'redact'
                  return (
                    <button
                      key={b.key}
                      onClick={() => !isDisabled && updateDecision(f.field_name, b.key)}
                      disabled={isDisabled}
                      title={isDisabled ? 'This field contains sensitive elements that are forced to be redacted by policy' : ''}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition-all duration-200 ${isDisabled ? 'opacity-30 cursor-not-allowed' : ''}`}
                      style={active
                        ? { background: b.color + '20', color: b.color, borderColor: b.color + '60' }
                        : { background: 'transparent', color: 'var(--text-3)', borderColor: 'var(--border)' }
                      }
                    >
                      {b.label}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-0 bg-bg-base border-t border-border py-4 -mx-4 px-4 sm:-mx-6 sm:px-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-text-3 text-sm">pei after:</span>
          <span className="font-mono text-lg font-semibold" style={{ color: peiColor(peiAfter) }}>
            {Math.round(peiAfter)}
          </span>
        </div>
        <div className="flex gap-3">
          <Button variant="ghost" onClick={handleApplyRedaction} disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {scan.redacted_image_url ? 're-generate' : 'generate redaction'}
          </Button>
          <Button onClick={handleDownload} disabled={!scan.redacted_image_url}>
            <Download size={14} />
            download safe document
          </Button>
          <Button variant="ghost" onClick={() => navigate(`/audit/${scan.scan_id}`)}>
            <FileText size={14} /> audit report
          </Button>
        </div>
      </div>
    </motion.div>
  )
}
