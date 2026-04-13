import { motion } from 'framer-motion'

export default function AuditTimeline({ events = [] }) {
  return (
    <div className="relative pl-6">
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />
      {events.map((event, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08 }}
          className="relative flex gap-4 pb-6 last:pb-0"
        >
          <div className="absolute left-[-17px] top-1.5 w-3 h-3 rounded-full bg-accent border-2 border-bg-base z-10" />
          <div className="flex-1">
            <p className="t-mono text-text-3 text-xs">{event.timestamp || event.time}</p>
            <p className="text-text-1 text-sm mt-0.5">{event.description || event.action}</p>
          </div>
        </motion.div>
      ))}
    </div>
  )
}
