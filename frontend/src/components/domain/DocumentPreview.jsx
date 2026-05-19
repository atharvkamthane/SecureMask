import { ImageOff } from 'lucide-react'

export default function DocumentPreview({ imageUrl, fields = [], decisions = {}, hoveredField, onFieldHover }) {
  if (!imageUrl) {
    return (
      <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] flex flex-col items-center justify-center py-20 text-text-3">
        <ImageOff size={40} className="mb-3 opacity-40" />
        <p className="text-sm">no document preview available</p>
        <p className="text-xs mt-1 opacity-60">upload a document to see the preview</p>
      </div>
    )
  }

  return (
    <div className="relative bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
      <img src={imageUrl} alt="Document" className="w-full h-auto block" />
      {fields.map((f, i) => {
        // Use percentage bounding box from the backend
        const bbox = f.bounding_box_pct || f.bounding_box
        if (!bbox) return null

        // bbox is an object with {x, y, width, height} in percentage (0-100)
        const x = bbox.x
        const y = bbox.y
        const w = bbox.width
        const h = bbox.height

        // Skip invalid boxes
        if (w <= 0 || h <= 0) return null

        const decision = decisions[f.field_name] || 'redact'
        const isHovered = hoveredField === f.field_name
        const color = decision === 'allow' ? 'var(--success)' : decision === 'mask' ? 'var(--warning)' : 'var(--danger)'

        return (
          <div
            key={`${f.field_name}-${i}`}
            onMouseEnter={() => onFieldHover?.(f.field_name)}
            onMouseLeave={() => onFieldHover?.(null)}
            className="absolute border-2 rounded-sm cursor-pointer transition-opacity"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: `${w}%`,
              height: `${h}%`,
              borderColor: color,
              backgroundColor: isHovered ? color + '20' : color + '08',
              boxShadow: isHovered ? `0 0 12px ${color}40` : 'none',
              transform: isHovered ? 'scale(1.02)' : 'scale(1)',
              opacity: hoveredField && !isHovered ? 0.3 : 1,
            }}
            title={`${f.field_name}: ${f.field_value || ''}`}
          >
            {/* Label tag */}
            {isHovered && (
              <div
                className="absolute -top-5 left-0 text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap font-medium"
                style={{ backgroundColor: color, color: '#000' }}
              >
                {f.field_name}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
