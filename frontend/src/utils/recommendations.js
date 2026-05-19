export const ACTION_COPY = {
  allow: {
    label: 'Allow',
    short: 'needed',
    tone: 'text-success',
    border: 'var(--success)',
    description: 'Keep visible because it is required for this purpose.',
  },
  mask: {
    label: 'Mask',
    short: 'partial',
    tone: 'text-warning',
    border: 'var(--warning)',
    description: 'Hide most of the value while leaving limited proof visible.',
  },
  redact: {
    label: 'Redact',
    short: 'remove',
    tone: 'text-danger',
    border: 'var(--danger)',
    description: 'Remove from the shared copy because it is excess or high-risk.',
  },
}

export const CONTEXT_GUIDANCE = {
  age_verification: {
    title: 'Age verification needs minimum proof only',
    body: 'Recommended defaults usually mask DOB, allow name if required, and redact ID numbers, address, QR, photo, and signature.',
  },
  identity_verification: {
    title: 'Identity verification should not expose the full document',
    body: 'Recommended defaults usually allow name and DOB, mask document numbers, and redact address, QR, MRZ, photo, signature, and unrelated fields.',
  },
  address_proof: {
    title: 'Address proof should focus on residence',
    body: 'Recommended defaults usually allow name and address, and redact document numbers, DOB, gender, photo, QR, MRZ, and signature.',
  },
  kyc_onboarding: {
    title: 'KYC needs more fields but still benefits from masking',
    body: 'Recommended defaults usually allow required identity/address fields, mask document numbers, and redact photo, QR, MRZ, signature, and extra fields.',
  },
  general_upload: {
    title: 'General upload has no declared necessity',
    body: 'Recommended defaults redact detected PII because no specific purpose justifies sharing personal fields.',
  },
}

export function recommendationCounts(fields = []) {
  return fields.reduce((acc, field) => {
    const action = field.suggested_action || field.redaction_decision || 'redact'
    acc[action] = (acc[action] || 0) + 1
    return acc
  }, { allow: 0, mask: 0, redact: 0 })
}

export function actionCopy(action) {
  return ACTION_COPY[action] || ACTION_COPY.redact
}
