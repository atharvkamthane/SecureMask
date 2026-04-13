const docs = [
  'Aadhaar Card', 'PAN Card', 'Passport', 'Driving License',
  'Voter ID', 'Ration Card', 'ESIC Card', 'Aadhaar Card', 'PAN Card',
  'Passport', 'Driving License', 'Voter ID', 'Ration Card', 'ESIC Card',
]

function Pill({ text }) {
  return (
    <span className="shrink-0 px-5 py-2 rounded-full bg-bg-surface-2 text-text-2 text-sm border border-border whitespace-nowrap">
      {text}
    </span>
  )
}

export default function DocTypeStrip() {
  return (
    <section className="py-12 overflow-hidden border-t border-b border-border bg-bg-base">
      {/* Row 1: scrolls left */}
      <div className="flex gap-3 mb-3 animate-scroll-left" style={{ width: 'max-content' }}>
        {[...docs, ...docs].map((d, i) => <Pill key={`r1-${i}`} text={d} />)}
      </div>
      {/* Row 2: scrolls right */}
      <div className="flex gap-3 animate-scroll-right" style={{ width: 'max-content' }}>
        {[...docs.reverse(), ...docs].map((d, i) => <Pill key={`r2-${i}`} text={d} />)}
      </div>
    </section>
  )
}
