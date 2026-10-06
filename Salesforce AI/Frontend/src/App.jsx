import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import TopNavbar from "./components/layout/TopNavbar";

import Home from "./pages/Home";

import Dashboard from "./pages/Dashboard";
import Overview from "./pages/dashboard/Overview";
import LicensesUsers from "./pages/dashboard/LicensesUsers";
import LimitsStorage from "./pages/dashboard/LimitsStorage";
import Metadata from "./pages/dashboard/Metadata";

import Workspace from "./pages/Workspace";
import Import from "./pages/Import";
import Migration from "./pages/Migration";
import Admin from "./pages/Admin";
import Settings from "./pages/Settings";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-zinc-950 dark:text-zinc-100">

        <TopNavbar />

        <Routes>

          {/* HOME */}
          <Route
            path="/"
            element={<Home />}
          />

          {/* SALESFORCE INTELLIGENCE */}
          <Route
            path="/dashboard"
            element={<Dashboard />}
          >
            <Route
              index
              element={
                <Navigate
                  to="overview"
                  replace
                />
              }
            />

            <Route
              path="overview"
              element={<Overview />}
            />

            <Route
              path="licenses"
              element={<LicensesUsers />}
            />

            <Route
              path="limits"
              element={<LimitsStorage />}
            />

            <Route
              path="metadata"
              element={<Metadata />}
            />
          </Route>

          {/* AI WORKSPACE */}
          <Route
            path="/workspace"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Workspace />
              </main>
            }
          />

          {/* IMPORT */}
          <Route
            path="/import"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Import />
              </main>
            }
          />

          {/* MIGRATION */}
          <Route
            path="/migration"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Migration />
              </main>
            }
          />

          {/* ADMIN */}
          <Route
            path="/admin"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Admin />
              </main>
            }
          />

          {/* SETTINGS */}
          <Route
            path="/settings"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Settings />
              </main>
            }
          />

          {/* FALLBACK */}
          <Route
            path="*"
            element={
              <Navigate
                to="/"
                replace
              />
            }
          />

        </Routes>

      </div>
    </BrowserRouter>
  );
}

export default App;