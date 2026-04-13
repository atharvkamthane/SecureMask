export function maskValue(value) {
  if (!value || value.length <= 4) return value || ''
  return value.slice(0, 4) + '****'
}

export function methodLabel(method) {
  const map = { regex: 'Regex', ner: 'NER', keyword_anchor: 'Keyword', image: 'Image' }
  return map[method] || method
}

export function methodColor(method) {
  const map = {
    regex: 'var(--violet)',
    ner: 'var(--accent)',
    keyword_anchor: 'var(--text-2)',
    image: 'var(--warning)',
  }
  return map[method] || 'var(--text-2)'
}
