import { useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./ui/App.tsx";
import { LoginScreen } from "@/components/auth/LoginScreen";
import { useAuthStore } from "@/state/authStore";

/**
 * Every data endpoint on the STRATA backend requires a Bearer token.
 *
 * LoginScreen already existed but was never mounted anywhere, so a signed-out
 * visitor silently received 401s from /spatial/search, /spatial/bbox and
 * /buildings/* and the UI showed "No backend record found" as if the database
 * were empty. This gate makes the token requirement explicit.
 */
function Root() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hydrateFromStorage = useAuthStore((state) => state.hydrateFromStorage);

  // Restore a token saved from a previous session before deciding what to show.
  useEffect(() => {
    hydrateFromStorage();
  }, [hydrateFromStorage]);

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return <App />;
}

createRoot(document.getElementById("root")!).render(<Root />);
