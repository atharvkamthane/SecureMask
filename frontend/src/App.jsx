import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import { ScanProvider } from './context/ScanContext'
import { AuthProvider } from './context/AuthContext'
import AppShell from './components/layout/AppShell'
import Toast from './components/ui/Toast'

// Lazy-loaded pages
const Landing = lazy(() => import('./pages/Landing'))
const Login = lazy(() => import('./pages/Login'))
const Signup = lazy(() => import('./pages/Signup'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Upload = lazy(() => import('./pages/Upload'))
const Detection = lazy(() => import('./pages/Detection'))
const NecessityCheck = lazy(() => import('./pages/NecessityCheck'))
const PEIScore = lazy(() => import('./pages/PEIScore'))
const RedactionPreview = lazy(() => import('./pages/RedactionPreview'))
const AuditReport = lazy(() => import('./pages/AuditReport'))
const ScanHistory = lazy(() => import('./pages/ScanHistory'))

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent/20 animate-pulse" />
        <span className="text-text-3 text-sm">loading...</span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <AuthProvider>
        <ScanProvider>
          <BrowserRouter>
            <Toast />
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* Public routes */}
                <Route path="/" element={<Landing />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />

                {/* Authenticated routes with AppShell */}
                <Route element={<AppShell />}>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/upload" element={<Upload />} />
                  <Route path="/detection" element={<Detection />} />
                  <Route path="/necessity" element={<NecessityCheck />} />
                  <Route path="/pei" element={<PEIScore />} />
                  <Route path="/redaction" element={<RedactionPreview />} />
                  <Route path="/audit/:scanId" element={<AuditReport />} />
                  <Route path="/history" element={<ScanHistory />} />
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ScanProvider>
      </AuthProvider>
    </MotionConfig>
  )
}
