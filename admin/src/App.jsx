import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./layout/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import Photos from "./pages/Photos.jsx";
import Tags from "./pages/Tags.jsx";
import Tagging from "./pages/Tagging.jsx";
import Users from "./pages/Users.jsx";
import UserDetail from "./pages/UserDetail.jsx";
import AiIngest from "./pages/AiIngest.jsx";
import FittingRequests from "./pages/FittingRequests.jsx";
import { getRole, getToken } from "./api.js";

function RequireAuth({ children }) {
  const t = getToken();
  if (!t) return <Navigate to="/login" replace />;
  return children;
}

function RoleRoute({ children, roles }) {
  const t = getToken();
  const r = getRole();
  if (!t) return <Navigate to="/login" replace />;
  if (!roles.includes(r)) return <Navigate to="/login" replace />;
  return children;
}

function HomeRoute() {
  const t = getToken();
  const r = getRole();
  if (!t) return <Navigate to="/login" replace />;
  if (r === "superuser") return <Dashboard />;
  if (r === "worker") return <Navigate to="/photos" replace />;
  return <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<HomeRoute />} />
          <Route
            path="/photos"
            element={
              <RoleRoute roles={["superuser", "worker"]}>
                <Photos />
              </RoleRoute>
            }
          />
          <Route
            path="/tags"
            element={
              <RoleRoute roles={["superuser", "worker"]}>
                <Tags />
              </RoleRoute>
            }
          />
          <Route
            path="/tagging"
            element={
              <RoleRoute roles={["superuser", "worker"]}>
                <Tagging />
              </RoleRoute>
            }
          />
          <Route
            path="/users"
            element={
              <RoleRoute roles={["superuser"]}>
                <Users />
              </RoleRoute>
            }
          />
          <Route
            path="/users/:userId"
            element={
              <RoleRoute roles={["superuser"]}>
                <UserDetail />
              </RoleRoute>
            }
          />
          <Route
            path="/fitting-requests"
            element={
              <RoleRoute roles={["superuser"]}>
                <FittingRequests />
              </RoleRoute>
            }
          />
          <Route
            path="/ai-ingest"
            element={
              <RoleRoute roles={["superuser", "worker"]}>
                <AiIngest />
              </RoleRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
