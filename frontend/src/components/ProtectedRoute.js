import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth();

  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background" data-testid="auth-loading">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" replace />;
  }
  if (roles && !roles.includes(user.role)) {
    const home = user.role === "SUPER_ADMIN" ? "/admin" : "/dashboard";
    return <Navigate to={home} replace />;
  }
  return children;
}
