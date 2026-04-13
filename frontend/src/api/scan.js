import client from './client'

export async function uploadDocument(file, context) {
  const form = new FormData()
  form.append('file', file)
  form.append('context', context)
  const { data } = await client.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function redactDocument(scanId, decisions) {
  const { data } = await client.post('/redact', {
    scan_id: scanId,
    decisions: decisions,
  })
  return data
}

export async function getAudit(scanId) {
  const { data } = await client.get(`/audit/${scanId}`)
  return data
}

export async function getScans() {
  const { data } = await client.get('/scans')
  return data
}

export async function scanText(text, context) {
  const { data } = await client.post('/scan-text', { text, context })
  return data
}
