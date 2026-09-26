import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./ui/App.tsx";

// Sign-in was removed from STRATA: the map is open on load and every backend
// endpoint is unauthenticated, so there is no token to restore or gate to pass.
createRoot(document.getElementById("root")!).render(<App />);
