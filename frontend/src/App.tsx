import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import AuthProvider from './auth/AuthProvider'
import ProtectedRoute from './components/auth/ProtectedRoute'
import PermissionGuard from './components/auth/PermissionGuard'
import RoleGuard from './components/auth/RoleGuard'
import SessionWarningDialog from './components/auth/SessionWarningDialog'
import { PERMISSIONS, ROLES } from './auth/auth.constants'
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
import Chat from './pages/Chat'
import RFQInbox from './pages/RFQInbox'
import RFQDetail from './pages/RFQDetail'
import GmailCallback from './pages/GmailCallback'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import UnauthorizedPage from './pages/UnauthorizedPage'
import SessionExpiredPage from './pages/SessionExpiredPage'
import AccountDisabledPage from './pages/AccountDisabledPage'
import UserManagementPage from './pages/UserManagementPage'
import ActiveSessionsPage from './pages/ActiveSessionsPage'
import AdminSessionsPage from './pages/AdminSessionsPage'
import AdminAuditLogsPage from './pages/AdminAuditLogsPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SessionWarningDialog />
        <Routes>
          {/* OAuth popup callback — rendered without app chrome */}
          <Route path="/gmail/callback" element={<GmailCallback />} />

          {/* Public authentication routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route path="/session-expired" element={<SessionExpiredPage />} />
          <Route path="/account-disabled" element={<AccountDisabledPage />} />

          {/* Protected application routes */}
          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={
              <PermissionGuard permissions={[PERMISSIONS.DASHBOARD_READ]}><Dashboard /></PermissionGuard>
            } />
            <Route path="/estimate/new" element={
              <PermissionGuard permissions={[PERMISSIONS.ESTIMATES_CREATE]}><NewEstimate /></PermissionGuard>
            } />
            <Route path="/drawing-costing/:jobId?" element={
              <PermissionGuard permissions={[PERMISSIONS.DRAWINGS_PROCESS]}><DrawingCosting /></PermissionGuard>
            } />
            <Route path="/weight-calculator" element={
              <RoleGuard roles={[ROLES.ESTIMATOR, ROLES.ADMIN]}><WeightCalculator /></RoleGuard>
            } />
            <Route path="/boq-parser" element={
              <PermissionGuard permissions={[PERMISSIONS.BOQ_PARSE]}><BOQParser /></PermissionGuard>
            } />
            <Route path="/excel-generator" element={
              <PermissionGuard permissions={[PERMISSIONS.EXCEL_GENERATE]}><ExcelGenerator /></PermissionGuard>
            } />
            <Route path="/quote-summary/:jobId?" element={
              <PermissionGuard permissions={[PERMISSIONS.QUOTATIONS_READ]}><QuoteSummary /></PermissionGuard>
            } />
            <Route path="/cover-letter" element={
              <PermissionGuard permissions={[PERMISSIONS.COVER_LETTERS_GENERATE]}><CoverLetterGenerator /></PermissionGuard>
            } />
            <Route path="/history" element={
              <PermissionGuard permissions={[PERMISSIONS.JOB_HISTORY_READ]}><JobHistory /></PermissionGuard>
            } />
            <Route path="/settings" element={
              <PermissionGuard permissions={[PERMISSIONS.SETTINGS_READ]}><Settings /></PermissionGuard>
            } />
            <Route path="/rfq" element={
              <PermissionGuard permissions={[PERMISSIONS.RFQ_READ]}><RFQInbox /></PermissionGuard>
            } />
            <Route path="/rfq/:rfqId" element={
              <PermissionGuard permissions={[PERMISSIONS.RFQ_READ]}><RFQDetail /></PermissionGuard>
            } />

            {/* Self-service — every authenticated user manages their own sessions */}
            <Route path="/sessions" element={<ActiveSessionsPage />} />

            {/* LLM inference playground — available to every authenticated user */}
            <Route path="/llm-extraction" element={<Chat />} />

            {/* Admin-only */}
            <Route path="/admin/users" element={
              <PermissionGuard permissions={[PERMISSIONS.USERS_READ]}><UserManagementPage /></PermissionGuard>
            } />
            <Route path="/admin/sessions" element={
              <PermissionGuard permissions={[PERMISSIONS.SESSIONS_READ]}><AdminSessionsPage /></PermissionGuard>
            } />
            <Route path="/admin/audit-logs" element={
              <PermissionGuard permissions={[PERMISSIONS.AUDIT_LOGS_READ]}><AdminAuditLogsPage /></PermissionGuard>
            } />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
