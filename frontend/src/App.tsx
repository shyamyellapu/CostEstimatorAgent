import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import NewEstimate from './pages/NewEstimate'
import DrawingReader from './pages/DrawingReader'
import DrawingCosting from './pages/DrawingCosting'
import WeightCalculator from './pages/WeightCalculator'
import BOQParser from './pages/BOQParser'
import ExcelGenerator from './pages/ExcelGenerator'
import QuoteSummary from './pages/QuoteSummary'
import CoverLetterGenerator from './pages/CoverLetterGenerator'
import JobHistory from './pages/JobHistory'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/estimate/new" element={<NewEstimate />} />
          <Route path="/drawing-reader" element={<DrawingReader />} />
          <Route path="/drawing-costing" element={<DrawingCosting />} />
          <Route path="/weight-calculator" element={<WeightCalculator />} />
          <Route path="/boq-parser" element={<BOQParser />} />
          <Route path="/excel-generator" element={<ExcelGenerator />} />
          <Route path="/quote-summary/:jobId?" element={<QuoteSummary />} />
          <Route path="/cover-letter" element={<CoverLetterGenerator />} />
          <Route path="/history" element={<JobHistory />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
