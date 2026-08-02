import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Shell from "./layout/Shell.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Menu from "./pages/Menu.jsx";
import OutletPhoto from "./pages/OutletPhoto.jsx";
import OrdersList from "./pages/OrdersList.jsx";
import OrderDetail from "./pages/OrderDetail.jsx";
import OrderCreate from "./pages/OrderCreate.jsx";
import OrderEdit from "./pages/OrderEdit.jsx";
import OrderGuidance from "./pages/OrderGuidance.jsx";
import PaymentsList from "./pages/PaymentsList.jsx";
import PaymentDetail from "./pages/PaymentDetail.jsx";
import PaymentCreate from "./pages/PaymentCreate.jsx";
import PaymentEdit from "./pages/PaymentEdit.jsx";
import ShipmentsList from "./pages/ShipmentsList.jsx";
import ShipmentDetail from "./pages/ShipmentDetail.jsx";
import ShipmentCreate from "./pages/ShipmentCreate.jsx";
import ShipmentEdit from "./pages/ShipmentEdit.jsx";
import {
  clearSession,
  hasOutletAccess,
  hasProductAccess,
  hasValidSession,
  hasWorkAccess,
  workHomePath,
} from "./api.js";

function RequireWork({ children }) {
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  if (!hasWorkAccess()) {
    clearSession();
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RequireProduct({ children }) {
  if (!hasProductAccess()) {
    return <Navigate to={workHomePath()} replace />;
  }
  return children;
}

function RequireOutlet({ children }) {
  if (!hasOutletAccess()) {
    return <Navigate to={workHomePath()} replace />;
  }
  return children;
}

function HomeRedirect() {
  return <Navigate to={workHomePath()} replace />;
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
          <Route path="/" element={<HomeRedirect />} />
          <Route
            path="/dashboard"
            element={
              <RequireProduct>
                <Dashboard />
              </RequireProduct>
            }
          />
          <Route
            path="/menu"
            element={
              <RequireProduct>
                <Menu />
              </RequireProduct>
            }
          />
          <Route
            path="/outlet"
            element={
              <RequireOutlet>
                <OutletPhoto />
              </RequireOutlet>
            }
          />
          <Route
            path="/orders"
            element={
              <RequireProduct>
                <OrdersList />
              </RequireProduct>
            }
          />
          <Route
            path="/orders/new"
            element={
              <RequireProduct>
                <OrderCreate />
              </RequireProduct>
            }
          />
          <Route
            path="/orders/:id"
            element={
              <RequireProduct>
                <OrderDetail />
              </RequireProduct>
            }
          />
          <Route
            path="/orders/:id/edit"
            element={
              <RequireProduct>
                <OrderEdit />
              </RequireProduct>
            }
          />
          <Route
            path="/for-order"
            element={
              <RequireProduct>
                <OrderGuidance />
              </RequireProduct>
            }
          />
          <Route
            path="/payments"
            element={
              <RequireProduct>
                <PaymentsList />
              </RequireProduct>
            }
          />
          <Route
            path="/payments/new"
            element={
              <RequireProduct>
                <PaymentCreate />
              </RequireProduct>
            }
          />
          <Route
            path="/payments/:id"
            element={
              <RequireProduct>
                <PaymentDetail />
              </RequireProduct>
            }
          />
          <Route
            path="/payments/:id/edit"
            element={
              <RequireProduct>
                <PaymentEdit />
              </RequireProduct>
            }
          />
          <Route
            path="/shipments"
            element={
              <RequireProduct>
                <ShipmentsList />
              </RequireProduct>
            }
          />
          <Route
            path="/shipments/new"
            element={
              <RequireProduct>
                <ShipmentCreate />
              </RequireProduct>
            }
          />
          <Route
            path="/shipments/:id"
            element={
              <RequireProduct>
                <ShipmentDetail />
              </RequireProduct>
            }
          />
          <Route
            path="/shipments/:id/edit"
            element={
              <RequireProduct>
                <ShipmentEdit />
              </RequireProduct>
            }
          />
        </Route>
        <Route path="*" element={<HomeRedirect />} />
      </Routes>
    </BrowserRouter>
  );
}
