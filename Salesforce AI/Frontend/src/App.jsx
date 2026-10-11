import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  Outlet,
} from "react-router-dom";

import TopNavbar from "./components/layout/TopNavbar";

import Home from "./pages/Home";
import Login from "./pages/Login";
import { useAuth } from "./context/AuthContext";
import { useOrg } from "./context/OrgContext";

function Protected() {
 const {user,loading,error}=useAuth();
 if(loading)return <div className="portal-loading">Loading your account…</div>;
 if(error)return <div role="alert" className="portal-loading">{error}</div>;
 return user ? <Outlet/> : <Navigate to="/login" replace/>;
}
function ConnectedWorkspace(){const {activeOrg,loading}=useOrg();return loading?<div className="portal-loading">Checking connection…</div>:activeOrg?<Workspace key={activeOrg.id}/>:<Navigate to="/" replace/>;}

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
import Profile from "./pages/Profile";

function PageNavbar() {
  const { pathname } = useLocation();
  const {user}=useAuth();
  if(!user)return null;

  return pathname === "/login" || pathname === "/workspace" ||
    pathname.startsWith("/workspace/")
    ? null
    : <TopNavbar />;
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-zinc-950 dark:text-zinc-100">
        <PageNavbar />

        <Routes>
          <Route path="/login" element={<Login/>}/>
          <Route element={<Protected/>}>
          <Route
            path="/"
            element={<Home />}
          />

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

          <Route
            path="/workspace"
            element={<ConnectedWorkspace />}
          />

          <Route
            path="/import"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Import />
              </main>
            }
          />

          <Route
            path="/migration"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Migration />
              </main>
            }
          />

          <Route
            path="/admin"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Admin />
              </main>
            }
          />

          <Route path="/profile" element={<Profile />} />
          <Route
            path="/settings"
            element={
              <main className="min-h-[calc(100vh-64px)]">
                <Settings />
              </main>
            }
          />

          <Route
            path="*"
            element={
              <Navigate
                to="/"
                replace
              />
            }
          />
        </Route>
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;