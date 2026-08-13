import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { ThemeProvider } from "./hooks/useTheme";
import { AuthProvider } from "./features/auth/AuthContext";
import { isDesktop } from "./lib/desktop";
import { BackendGate } from "./components/common/BackendGate";
import { Titlebar } from "./components/layout/Titlebar";
import "./index.css";

// Marks the document so CSS can reserve room for the custom titlebar. Set
// before first paint so the layout never shifts once the shell mounts.
if (isDesktop()) document.documentElement.dataset.desktop = "";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        {/* Above the gate on purpose: with `decorations: false` this bar is the
            only way to minimise or close, so it must exist during the splash
            and on the login screen too, not just once signed in. */}
        <Titlebar />
        {/* Auth mounts only once the backend answers — otherwise its very first
            request races the sidecar's startup and always loses. */}
        <BackendGate>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </BackendGate>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
