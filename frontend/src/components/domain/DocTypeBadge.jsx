import Badge from '../ui/Badge'
import { DOC_TYPES } from '../../constants/docTypes'

export default function DocTypeBadge({ docType }) {
  const info = DOC_TYPES[docType] || DOC_TYPES.unknown
  return <Badge variant="accent">{info.label}</Badge>
}
