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
import { getRole, getToken } from "./api.js";

function SuperRoute({ children }) {
  const t = getToken();
  const r = getRole();
  if (!t) return <Navigate to="/login" replace />;
  if (r !== "superuser") return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/photos" element={<Photos />} />
          <Route path="/tags" element={<Tags />} />
          <Route path="/tagging" element={<Tagging />} />
          <Route
            path="/users"
            element={
              <SuperRoute>
                <Users />
              </SuperRoute>
            }
          />
          <Route
            path="/users/:userId"
            element={
              <SuperRoute>
                <UserDetail />
              </SuperRoute>
            }
          />
          <Route
            path="/ai-ingest"
            element={
              <SuperRoute>
                <AiIngest />
              </SuperRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
