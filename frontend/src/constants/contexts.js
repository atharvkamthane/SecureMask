export const CONTEXTS = [
  { value: 'age_verification', label: 'Age Verification' },
  { value: 'identity_verification', label: 'Identity Verification' },
  { value: 'address_proof', label: 'Address Proof' },
  { value: 'kyc_onboarding', label: 'KYC Onboarding' },
  { value: 'general_upload', label: 'General Upload' },
]

export const CONTEXT_MAP = Object.fromEntries(CONTEXTS.map(c => [c.value, c.label]))
