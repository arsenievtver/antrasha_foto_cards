import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Shell from "./layout/Shell.jsx";
import Login from "./pages/Login.jsx";
import OrdersList from "./pages/OrdersList.jsx";
import OrderDetail from "./pages/OrderDetail.jsx";
import OrderCreate from "./pages/OrderCreate.jsx";
import PaymentsList from "./pages/PaymentsList.jsx";
import PaymentDetail from "./pages/PaymentDetail.jsx";
import PaymentCreate from "./pages/PaymentCreate.jsx";
import ShipmentsList from "./pages/ShipmentsList.jsx";
import ShipmentDetail from "./pages/ShipmentDetail.jsx";
import ShipmentCreate from "./pages/ShipmentCreate.jsx";
import { clearSession, hasProductAccess, hasValidSession } from "./api.js";

function RequireWork({ children }) {
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  if (!hasProductAccess()) {
    clearSession();
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireWork>
              <Shell />
            </RequireWork>
          }
        >
          <Route path="/" element={<Navigate to="/orders" replace />} />
          <Route path="/orders" element={<OrdersList />} />
          <Route path="/orders/new" element={<OrderCreate />} />
          <Route path="/orders/:id" element={<OrderDetail />} />
          <Route path="/payments" element={<PaymentsList />} />
          <Route path="/payments/new" element={<PaymentCreate />} />
          <Route path="/payments/:id" element={<PaymentDetail />} />
          <Route path="/shipments" element={<ShipmentsList />} />
          <Route path="/shipments/new" element={<ShipmentCreate />} />
          <Route path="/shipments/:id" element={<ShipmentDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/orders" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
