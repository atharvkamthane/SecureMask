import Badge from '../ui/Badge'
import { peiLabel } from '../../utils/peiColor'

export default function RiskBadge({ score }) {
  const label = peiLabel(score)
  const variant = label === 'high' ? 'high' : label === 'medium' ? 'medium' : 'low'
  return <Badge variant={variant} pulse={label === 'high'}>{label} risk</Badge>
}
