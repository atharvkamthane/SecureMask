export function maskValue(value) {
  if (!value || value.length <= 4) return value || ''
  return value.slice(0, 4) + '****'
}

export function methodLabel(method) {
  const map = {
    regex: 'Regex',
    regex_fuzzy: 'Regex + fuzzy',
    ner: 'NER',
    keyword_anchor: 'Keyword',
    image: 'Image',
    qr: 'QR',
    mrz: 'MRZ',
  }
  return map[method] || method
}

export function methodColor(method) {
  const map = {
    regex: 'var(--violet)',
    regex_fuzzy: 'var(--violet)',
    ner: 'var(--accent)',
    keyword_anchor: 'var(--text-2)',
    image: 'var(--warning)',
    qr: 'var(--success)',
    mrz: 'var(--success)',
  }
  return map[method] || 'var(--text-2)'
}
