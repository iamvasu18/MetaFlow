import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import AuthProvider from "./context/AuthContext";
import "./index.css";

import { ThemeProvider } from "./context/ThemeContext";
import OrgProvider from "./context/OrgContext";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider><OrgProvider>
        <App />
      </OrgProvider></AuthProvider>
    </ThemeProvider>
  </StrictMode>
);