import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import StartupGate from "./StartupGate";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Desktop root element is missing.");
}

createRoot(root).render(
  <StrictMode>
    <StartupGate>
      <App />
    </StartupGate>
  </StrictMode>,
);
