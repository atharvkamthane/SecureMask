import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip as ReTooltip, ResponsiveContainer, Cell } from 'recharts'
import { PlusCircle, ArrowRight } from 'lucide-react'
import { getScans } from '../api/scan'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import { peiColor, peiLabel } from '../utils/peiColor'
import { DOC_TYPES } from '../constants/docTypes'
import { useAnimatedCount } from '../hooks/useAnimatedCount'

function StatCard({ label, value, color }) {
  const animated = useAnimatedCount(value, 800)
  return (
    <Card hover={false} className="flex flex-col gap-2 p-6">
      <span className="t-label text-text-2">{label}</span>
      <span className="font-mono text-[28px] font-semibold leading-none" style={{ color: color || 'var(--text-1)' }}>
        {typeof value === 'number' ? Math.round(animated) : value}
      </span>
    </Card>
  )
}

function EmptyState() {
  return (
    <Card hover={false} className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-xl bg-bg-surface-2 border border-border flex items-center justify-center text-text-3 mb-4">
        <PlusCircle size={24} />
      </div>
      <h3 className="text-text-1 font-medium">no scans yet</h3>
      <p className="text-text-3 text-sm mt-1 mb-4">upload a document to get started</p>
      <Link to="/upload">
        <Button size="sm">start your first scan</Button>
      </Link>
    </Card>
  )
}

export default function Dashboard() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getScans()
      .then(data => setScans(Array.isArray(data) ? data : data?.scans || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const recent = scans.slice(0, 10)
  const total = scans.length
  const avgBefore = total > 0 ? scans.reduce((a, s) => a + (s.pei_before || 0), 0) / total : 0
  const avgAfter = total > 0 ? scans.reduce((a, s) => a + (s.pei_after || s.pei_before || 0), 0) / total : 0
  const reduction = avgBefore > 0 ? Math.round(((avgBefore - avgAfter) / avgBefore) * 100) : 0

  // Field exposure data for chart
  const fieldCounts = {}
  scans.forEach(s => {
    (s.detected_fields || []).forEach(f => {
      if (!f.required) fieldCounts[f.field_name] = (fieldCounts[f.field_name] || 0) + 1
    })
  })
  const chartData = Object.entries(fieldCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8)

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-40 animate-shimmer rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-24 animate-shimmer rounded-[var(--r-lg)]" />)}
        </div>
        <div className="h-64 animate-shimmer rounded-[var(--r-lg)]" />
      </div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="t-h2 text-text-1">dashboard</h1>
        <Link to="/upload"><Button>new scan</Button></Link>
      </div>

      {total === 0 ? <EmptyState /> : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="total scans" value={total} />
            <StatCard label="avg pei before" value={avgBefore} color={peiColor(avgBefore)} />
            <StatCard label="avg pei after" value={avgAfter} color={peiColor(avgAfter)} />
            <StatCard label="risk reduction" value={`${reduction}%`} color="var(--success)" />
          </div>

          {/* Recent scans table */}
          <Card hover={false}>
            <h3 className="t-h3 text-text-1 mb-4">recent scans</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left t-label text-text-3 pb-3 pr-4">file</th>
                    <th className="text-left t-label text-text-3 pb-3 pr-4">type</th>
                    <th className="text-left t-label text-text-3 pb-3 pr-4">pei</th>
                    <th className="text-left t-label text-text-3 pb-3 pr-4">risk</th>
                    <th className="text-right t-label text-text-3 pb-3">action</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((s, i) => (
                    <tr key={i} className="border-b border-border last:border-0 hover:bg-bg-surface-3 transition-colors">
                      <td className="py-3 pr-4 text-sm text-text-1">{s.filename || `scan-${i + 1}`}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="accent">{DOC_TYPES[s.document_type]?.short || s.document_type || '—'}</Badge>
                      </td>
                      <td className="py-3 pr-4">
                        <span className="t-mono font-medium" style={{ color: peiColor(s.pei_before || 0) }}>
                          {Math.round(s.pei_before || 0)}
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        <Badge variant={peiLabel(s.pei_before || 0)} pulse={peiLabel(s.pei_before || 0) === 'high'}>
                          {peiLabel(s.pei_before || 0)}
                        </Badge>
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => navigate(`/audit/${s.scan_id}`)}
                          className="text-accent text-sm hover:text-accent-hover transition-colors inline-flex items-center gap-1"
                        >
                          view <ArrowRight size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Chart */}
          {chartData.length > 0 && (
            <Card hover={false}>
              <h3 className="t-h3 text-text-1 mb-4">most exposed fields across scans</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
                  <XAxis type="number" tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={{ stroke: 'var(--border)' }} />
                  <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-2)', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={`url(#barGrad)`} />
                    ))}
                  </Bar>
                  <defs>
                    <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="var(--danger)" />
                      <stop offset="100%" stopColor="var(--warning)" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}
    </motion.div>
  )
}
