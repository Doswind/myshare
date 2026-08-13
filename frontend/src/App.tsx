import { Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import DashboardPage from "@/pages/DashboardPage";
import FundListPage from "@/pages/FundListPage";
import FundDetailPage from "@/pages/FundDetailPage";
import StockDetailPage from "@/pages/StockDetailPage";
import StockListPage from "@/pages/StockListPage";
import SettingsPage from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/funds" element={<FundListPage />} />
        <Route path="/funds/:code" element={<FundDetailPage />} />
        <Route path="/stocks" element={<StockListPage />} />
        <Route path="/stocks/:code" element={<StockDetailPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
