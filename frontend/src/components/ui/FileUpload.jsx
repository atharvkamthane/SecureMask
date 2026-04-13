import { useCallback, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload } from 'lucide-react'

export default function FileUpload({ onFile, accept = '.jpg,.jpeg,.png,.pdf' }) {
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState(null)
  const inputRef = useRef()

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer?.files?.[0]
    if (file) { setFileName(file.name); onFile(file) }
  }, [onFile])

  const handleChange = useCallback((e) => {
    const file = e.target.files?.[0]
    if (file) { setFileName(file.name); onFile(file) }
  }, [onFile])

  return (
    <motion.div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      animate={dragging ? { borderColor: 'var(--accent)', backgroundColor: 'rgba(200,169,110,0.06)' } : {}}
      className="relative cursor-pointer border-2 border-dashed border-border rounded-[var(--r-xl)] p-12 flex flex-col items-center gap-3 transition-colors duration-200 hover:border-border-strong"
    >
      <input ref={inputRef} type="file" accept={accept} onChange={handleChange} className="hidden" />
      <motion.div animate={dragging ? { scale: 1.15 } : { scale: 1 }} transition={{ type: 'spring', stiffness: 300 }}>
        <Upload size={28} className="text-text-3" />
      </motion.div>
      <p className="text-text-2 text-sm text-center">
        {fileName ? <span className="text-text-1">{fileName}</span> : 'drop your document here'}
      </p>
      <p className="text-text-3 text-xs">supports jpg, png, pdf, screenshot</p>
    </motion.div>
  )
}
