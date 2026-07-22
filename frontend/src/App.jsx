import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import VerificationPending from './pages/VerificationPending';
import VerifyEmail from './pages/VerifyEmail';
import Settings from './pages/Settings';
import BudgetSetup from './pages/BudgetSetup';
import Savings from './pages/Savings';
import Reports from './pages/Reports';
import AppLayout from './components/AppLayout';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/verify-email-sent" element={<VerificationPending />} />
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/dashboard/monthly" element={<Dashboard monthly />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/savings" element={<Savings />} />
          <Route path="/budget" element={<BudgetSetup />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
