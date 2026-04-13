import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, ArrowRight } from 'lucide-react'
import { getScans } from '../api/scan'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { peiColor, peiLabel } from '../utils/peiColor'
import { DOC_TYPES } from '../constants/docTypes'
import { CONTEXT_MAP } from '../constants/contexts'

export default function ScanHistory() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getScans()
      .then(data => setScans(Array.isArray(data) ? data : data?.scans || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let result = scans
    if (filter !== 'all') {
      result = result.filter(s => peiLabel(s.pei_before || 0) === filter)
    }
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(s =>
        (s.filename || '').toLowerCase().includes(q) ||
        (s.document_type || '').toLowerCase().includes(q)
      )
    }
    return result
  }, [scans, filter, search])

  const filters = ['all', 'high', 'medium', 'low']

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-shimmer rounded-lg" />
        {[1,2,3,4].map(i => <div key={i} className="h-16 animate-shimmer rounded-[var(--r-lg)]" />)}
      </div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <h1 className="t-h2 text-text-1">scan history</h1>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="flex gap-2">
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors
                ${filter === f
                  ? 'bg-accent-dim border-accent/40 text-accent'
                  : 'border-border text-text-3 hover:text-text-2 hover:border-border-strong'
                }`}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-[280px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-3" />
          <input
            type="text"
            placeholder="search scans..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-[var(--r-md)] bg-bg-surface-2 border border-border text-text-1 text-sm placeholder:text-text-3 outline-none focus:border-accent transition-colors"
          />
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 ? (
        <Card hover={false} className="flex flex-col items-center py-16 text-center">
          <p className="text-text-2">no scans found</p>
          <p className="text-text-3 text-sm mt-1 mb-4">
            {scans.length === 0 ? 'start by scanning a document' : 'try adjusting your filters'}
          </p>
          {scans.length === 0 && (
            <Button size="sm" onClick={() => navigate('/upload')}>new scan</Button>
          )}
        </Card>
      ) : (
        /* Table */
        <Card hover={false}>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left t-label text-text-3 pb-3 pr-4">file</th>
                  <th className="text-left t-label text-text-3 pb-3 pr-4">type</th>
                  <th className="text-left t-label text-text-3 pb-3 pr-4">context</th>
                  <th className="text-left t-label text-text-3 pb-3 pr-4">pei before</th>
                  <th className="text-left t-label text-text-3 pb-3 pr-4">pei after</th>
                  <th className="text-left t-label text-text-3 pb-3 pr-4">date</th>
                  <th className="text-right t-label text-text-3 pb-3">action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <tr
                    key={i}
                    className="border-b border-border last:border-0 hover:bg-bg-surface-3 transition-colors cursor-pointer"
                    onClick={() => navigate(`/audit/${s.scan_id}`)}
                  >
                    <td className="py-3 pr-4 text-sm text-text-1">{s.filename || `scan-${i + 1}`}</td>
                    <td className="py-3 pr-4">
                      <Badge variant="accent">{DOC_TYPES[s.document_type]?.short || s.document_type || '—'}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-text-2 text-sm">{CONTEXT_MAP[s.declared_context] || s.declared_context || '—'}</td>
                    <td className="py-3 pr-4">
                      <span className="t-mono font-medium" style={{ color: peiColor(s.pei_before || 0) }}>
                        {Math.round(s.pei_before || 0)}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="t-mono font-medium" style={{ color: peiColor(s.pei_after || s.pei_before || 0) }}>
                        {Math.round(s.pei_after || s.pei_before || 0)}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-text-3 text-xs">{s.timestamp || s.created_at || '—'}</td>
                    <td className="py-3 text-right">
                      <span className="text-accent text-sm inline-flex items-center gap-1">
                        view <ArrowRight size={12} />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </motion.div>
  )
}
