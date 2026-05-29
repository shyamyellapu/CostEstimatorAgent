import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import NewEstimate from './pages/NewEstimate'
import DrawingCosting from './pages/DrawingCosting'
import WeightCalculator from './pages/WeightCalculator'
import BOQParser from './pages/BOQParser'
import ExcelGenerator from './pages/ExcelGenerator'
import QuoteSummary from './pages/QuoteSummary'
import CoverLetterGenerator from './pages/CoverLetterGenerator'
import JobHistory from './pages/JobHistory'
import Settings from './pages/Settings'
import RFQInbox from './pages/RFQInbox'
import RFQDetail from './pages/RFQDetail'
import GmailCallback from './pages/GmailCallback'
import { api } from './api/client'

export default function App() {
  useEffect(() => {
    api.get('/ai/info').then(res => {
      const info = res.data
      const fallback = info.fallback_provider
        ? ` | Fallback: ${info.fallback_provider} (${info.fallback_model})`
        : ''
      console.log(
        `%c[AI Model] Provider: ${info.provider} | Primary: ${info.primary_model}${fallback}`,
        'color: #4ade80; font-weight: bold;'
      )
    }).catch(() => {
      console.warn('[AI Model] Could not fetch AI provider info from server.')
    })
  }, [])
  return (
    <BrowserRouter>
      <Routes>
        {/* OAuth popup callback — rendered without app chrome */}
        <Route path="/gmail/callback" element={<GmailCallback />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/estimate/new" element={<NewEstimate />} />
          <Route path="/drawing-costing" element={<DrawingCosting />} />
          <Route path="/weight-calculator" element={<WeightCalculator />} />
          <Route path="/boq-parser" element={<BOQParser />} />
          <Route path="/excel-generator" element={<ExcelGenerator />} />
          <Route path="/quote-summary/:jobId?" element={<QuoteSummary />} />
          <Route path="/cover-letter" element={<CoverLetterGenerator />} />
          <Route path="/history" element={<JobHistory />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/rfq" element={<RFQInbox />} />
          <Route path="/rfq/:rfqId" element={<RFQDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
