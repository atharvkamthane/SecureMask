import Badge from '../ui/Badge'
import { methodLabel } from '../../utils/fieldHelpers'

export default function FieldTag({ field }) {
  return (
    <Badge variant={field.required ? 'low' : 'high'}>
      {field.field_name} · {methodLabel(field.detection_method)}
    </Badge>
  )
}
