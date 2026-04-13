import { Toaster } from 'react-hot-toast'

export default function Toast() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: 'var(--bg-surface)',
          color: 'var(--text-1)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--r-md)',
          fontSize: '13px',
        },
        success: { iconTheme: { primary: 'var(--success)', secondary: '#080808' } },
        error: { iconTheme: { primary: 'var(--danger)', secondary: '#080808' } },
      }}
    />
  )
}
