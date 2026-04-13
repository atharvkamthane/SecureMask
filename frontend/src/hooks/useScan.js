import { useContext } from 'react'
import { ScanContext } from '../context/ScanContext'

export function useScan() {
  return useContext(ScanContext)
}
