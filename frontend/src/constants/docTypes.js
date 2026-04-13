export const DOC_TYPES = {
  aadhaar: { label: 'Aadhaar Card', short: 'Aadhaar' },
  pan: { label: 'PAN Card', short: 'PAN' },
  driving_license: { label: 'Driving License', short: 'DL' },
  passport: { label: 'Passport', short: 'Passport' },
  voter_id: { label: 'Voter ID', short: 'Voter ID' },
  ration_card: { label: 'Ration Card', short: 'Ration' },
  esic: { label: 'ESIC Card', short: 'ESIC' },
  unknown: { label: 'Unknown Document', short: 'Unknown' },
}

export const DOC_TYPE_LABELS = Object.entries(DOC_TYPES).map(([value, { label }]) => ({ value, label }))
