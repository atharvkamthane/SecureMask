import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { useScan } from '../hooks/useScan'
import { uploadDocument } from '../api/scan'
import { CONTEXTS } from '../constants/contexts'
import StepIndicator from '../components/ui/StepIndicator'
import FileUpload from '../components/ui/FileUpload'
import Button from '../components/ui/Button'

export default function Upload() {
  const [file, setFile] = useState(null)
  const [context, setContext] = useState('identity_verification')
  const [loading, setLoading] = useState(false)
  const { setScan } = useScan()
  const navigate = useNavigate()

  const currentStep = file ? (loading ? 2 : 1) : 0

  const handleScan = useCallback(async () => {
    if (!file) return
    setLoading(true)
    try {
      const result = await uploadDocument(file, context)
      setScan(result)
      toast.success('scan complete')
      navigate('/detection')
    } catch (err) {
      // Error handled by axios interceptor
    } finally {
      setLoading(false)
    }
  }, [file, context, setScan, navigate])

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="max-w-[560px] mx-auto space-y-8">
      <div className="text-center">
        <h1 className="t-h2 text-text-1">scan a document</h1>
        <p className="text-text-2 text-sm mt-2">upload, configure, detect</p>
      </div>

      <StepIndicator steps={['Upload', 'Configure', 'Scan']} current={currentStep} />

      {/* File upload zone */}
      <FileUpload onFile={setFile} />

      {/* Context selector */}
      <div className="space-y-2">
        <label className="t-small text-text-2">why are you sharing this document?</label>
        <select
          value={context}
          onChange={e => setContext(e.target.value)}
          className="w-full px-3 py-2.5 rounded-[var(--r-md)] bg-bg-surface-2 border border-border text-text-1 text-sm outline-none focus:border-accent transition-colors appearance-none cursor-pointer"
        >
          {CONTEXTS.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <p className="text-text-3 text-xs italic leading-relaxed">
          this powers the necessity classifier — only truly required fields are marked safe
        </p>
      </div>

      {/* Scan button */}
      <Button
        onClick={handleScan}
        disabled={!file || loading}
        className="w-full"
        size="lg"
      >
        {loading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            scanning...
          </>
        ) : 'scan document'}
      </Button>
    </motion.div>
  )
}
