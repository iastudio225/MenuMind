import React from "react";
import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Onboarding from "@/pages/Onboarding";
import DashboardLayout from "@/layouts/DashboardLayout";
import Overview from "@/pages/dashboard/Overview";
import UsersPage from "@/pages/dashboard/UsersPage";
import SettingsPage from "@/pages/dashboard/SettingsPage";
import AiTestConsole from "@/pages/dashboard/AiTestConsole";
import MenuPage from "@/pages/dashboard/MenuPage";
import WeeklyMenuPage from "@/pages/dashboard/WeeklyMenuPage";
import OrdersPage from "@/pages/dashboard/OrdersPage";
import CustomersPage from "@/pages/dashboard/CustomersPage";
import DeliveryPage from "@/pages/dashboard/DeliveryPage";
import StoreFront from "@/pages/StoreFront";
import SuperAdmin from "@/pages/admin/SuperAdmin";

function RootRedirect() {
  const { user } = useAuth();
  if (user === null) return null;
  if (user === false) return <Landing />;
  if (user.role === "SUPER_ADMIN") return <Navigate to="/admin" replace />;
  return <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/order/:publicId" element={<StoreFront />} />

            <Route
              path="/onboarding"
              element={
                <ProtectedRoute roles={["RESTAURANT_OWNER", "RESTAURANT_MANAGER"]}>
                  <Onboarding />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute roles={["RESTAURANT_OWNER", "RESTAURANT_MANAGER", "RESTAURANT_STAFF"]}>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Overview />} />
              <Route path="orders" element={<OrdersPage />} />
              <Route path="menu" element={<MenuPage />} />
              <Route path="weekly-menu" element={<WeeklyMenuPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="delivery" element={<DeliveryPage />} />
              <Route path="ai" element={<AiTestConsole />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>

            <Route
              path="/admin"
              element={
                <ProtectedRoute roles={["SUPER_ADMIN"]}>
                  <SuperAdmin />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
