import { Navigate, Route, Routes } from "react-router-dom";
import { hasGiftAccess, hasValidSession } from "./api.js";
import Shell from "./layout/Shell.jsx";
import CertificatePage from "./pages/CertificatePage.jsx";
import CertificatesPage from "./pages/CertificatesPage.jsx";
import Login from "./pages/Login.jsx";

function RequireGift({ children }) {
  if (!hasValidSession() || !hasGiftAccess()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/certificates/:id" element={<CertificatePage />} />
      <Route
        path="/"
        element={
          <RequireGift>
            <Shell />
          </RequireGift>
        }
      >
        <Route index element={<CertificatesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
