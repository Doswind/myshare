import { Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { PrivateRoute } from "@/components/PrivateRoute";
import DashboardPage from "@/pages/DashboardPage";
import FundListPage from "@/pages/FundListPage";
import FundDetailPage from "@/pages/FundDetailPage";
import StockDetailPage from "@/pages/StockDetailPage";
import StockListPage from "@/pages/StockListPage";
import SettingsPage from "@/pages/SettingsPage";
import LoginPage from "@/pages/LoginPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";
import ProfilePage from "@/pages/ProfilePage";
import UsersAdminPage from "@/pages/admin/UsersAdminPage";
import RolesAdminPage from "@/pages/admin/RolesAdminPage";
import AuditLogPage from "@/pages/admin/AuditLogPage";

export default function App() {
  return (
    <Routes>
      {/* 无需登录 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* 需登录 */}
      <Route
        element={
          <PrivateRoute>
            <AppShell />
          </PrivateRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/funds" element={<FundListPage />} />
        <Route path="/funds/:code" element={<FundDetailPage />} />
        <Route path="/stocks" element={<StockListPage />} />
        <Route path="/stocks/:code" element={<StockDetailPage />} />
        <Route path="/settings" element={
          <PrivateRoute permission="settings:view">
            <SettingsPage />
          </PrivateRoute>
        } />
        <Route path="/profile" element={<ProfilePage />} />
        {/* 管理员后台 */}
        <Route path="/admin/users" element={
          <PrivateRoute permission="users:view">
            <UsersAdminPage />
          </PrivateRoute>
        } />
        <Route path="/admin/roles" element={
          <PrivateRoute permission="roles:view">
            <RolesAdminPage />
          </PrivateRoute>
        } />
        <Route path="/admin/audit" element={
          <PrivateRoute permission="audit:view">
            <AuditLogPage />
          </PrivateRoute>
        } />
      </Route>
    </Routes>
  );
}
