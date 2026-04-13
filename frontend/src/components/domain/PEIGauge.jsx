import { motion } from 'framer-motion'
import { useAnimatedCount } from '../../hooks/useAnimatedCount'
import { peiColor, peiLabel } from '../../utils/peiColor'

export default function PEIGauge({ score = 0, size = 200 }) {
  const animated = useAnimatedCount(score, 1200)
  const radius = (size - 24) / 2
  const circumference = Math.PI * radius
  const offset = circumference * (1 - Math.min(score, 100) / 100)
  const color = peiColor(score)
  const label = peiLabel(score)

  return (
    <div className="flex flex-col items-center gap-3">
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        {/* Track */}
        <path
          d={`M 12 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 12} ${size / 2}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Fill arc */}
        <motion.path
          d={`M 12 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 12} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
        {/* Score text */}
        <text
          x={size / 2}
          y={size / 2 - 8}
          textAnchor="middle"
          fill={color}
          fontFamily="var(--font-mono)"
          fontSize="42"
          fontWeight="700"
        >
          {Math.round(animated)}
        </text>
      </svg>
      <span
        className="t-label px-3 py-1 rounded-full"
        style={{ color, backgroundColor: `${color}1A` }}
      >
        {label} risk
      </span>
    </div>
  )
}
