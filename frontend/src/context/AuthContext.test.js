import React, { act } from "react";
import { createRoot } from "react-dom/client";
import api from "../lib/api";
import { AuthProvider, useAuth } from "./AuthContext";
import ProtectedRoute from "../components/ProtectedRoute";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("react-router-dom", () => ({
  Navigate: ({ to }) => <span data-testid="redirect-target">{to}</span>,
}));

jest.mock("../lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
  SESSION_INVALIDATED_EVENT: "menumind:session-invalidated",
}));

describe("SUPER_ADMIN route session handling", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.resetAllMocks();
  });

  async function renderRoutes() {
    await act(async () => {
      root.render(
        <AuthProvider>
          <RefreshButton />
          <ProtectedRoute roles={["SUPER_ADMIN"]}><div>Admin dashboard</div></ProtectedRoute>
        </AuthProvider>
      );
    });
  }

  function RefreshButton() {
    const { refresh } = useAuth();
    return <button data-testid="refresh-session" onClick={refresh}>Refresh session</button>;
  }

  test("keeps an authenticated SUPER_ADMIN on the admin route", async () => {
    api.get.mockResolvedValue({ data: { role: "SUPER_ADMIN" } });
    await renderRoutes();

    expect(container.textContent).toContain("Admin dashboard");
    expect(container.textContent).not.toContain("/login");
  });

  test("redirects an unauthenticated visitor after auth/me returns 401", async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
    await renderRoutes();

    expect(container.textContent).toContain("/login");
    expect(container.textContent).not.toContain("Admin dashboard");
  });

  test("redirects an authenticated user without SUPER_ADMIN role", async () => {
    api.get.mockResolvedValue({ data: { role: "RESTAURANT_OWNER" } });
    await renderRoutes();

    expect(container.textContent).toContain("/dashboard");
    expect(container.textContent).not.toContain("Admin dashboard");
  });

  test("moves to anonymous state after the refresh failure event", async () => {
    api.get.mockResolvedValue({ data: { role: "SUPER_ADMIN" } });
    await renderRoutes();
    expect(container.textContent).toContain("Admin dashboard");

    await act(async () => {
      window.dispatchEvent(new Event("menumind:session-invalidated"));
    });

    expect(container.textContent).toContain("/login");
    expect(container.textContent).not.toContain("Admin dashboard");
  });

  test("keeps an existing session on a temporary auth network error", async () => {
    api.get
      .mockResolvedValueOnce({ data: { role: "SUPER_ADMIN" } })
      .mockRejectedValueOnce(new Error("temporary network failure"));
    await renderRoutes();

    await act(async () => {
      container.querySelector('[data-testid="refresh-session"]').click();
    });

    expect(container.textContent).toContain("Admin dashboard");
    expect(container.textContent).not.toContain("/login");
  });
});
