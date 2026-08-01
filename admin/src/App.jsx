import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./layout/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import PhotoRatings from "./pages/PhotoRatings.jsx";
import Photos from "./pages/Photos.jsx";
import Tags from "./pages/Tags.jsx";
import Tagging from "./pages/Tagging.jsx";
import Users from "./pages/Users.jsx";
import UserDetail from "./pages/UserDetail.jsx";
import AiIngest from "./pages/AiIngest.jsx";
import FittingRequests from "./pages/FittingRequests.jsx";
import Campaigns from "./pages/Campaigns.jsx";
import PromoBanners from "./pages/PromoBanners.jsx";
import HeroBanners from "./pages/HeroBanners.jsx";
import HomeV2GenderCards from "./pages/HomeV2GenderCards.jsx";
import PushNotifications from "./pages/PushNotifications.jsx";
import Seasons from "./pages/Seasons.jsx";
import Brands from "./pages/Brands.jsx";
import BrandOrders from "./pages/BrandOrders.jsx";
import Payments from "./pages/Payments.jsx";
import Shipments from "./pages/Shipments.jsx";
import FxRates from "./pages/FxRates.jsx";
import { getPermissions, getRole, hasPermission, hasValidSession } from "./api.js";

function RequireAuth({ children }) {
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  return children;
}

function RoleRoute({ children, roles }) {
  const r = getRole();
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  if (!roles.includes(r)) return <Navigate to="/login" replace />;
  return children;
}

function PermissionRoute({ children, permission, roles = ["superuser", "worker"] }) {
  const r = getRole();
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  if (!roles.includes(r)) return <Navigate to="/login" replace />;
  if (r === "superuser" || hasPermission(permission)) return children;
  return <Navigate to="/" replace />;
}

const HOME_FALLBACKS = [
  ["stats", "/"],
  ["photos", "/photos"],
  ["clients", "/fitting-requests"],
  ["ads", "/campaigns"],
  ["product", "/seasons"],
];

function firstAllowedPath() {
  if (getRole() === "superuser") return "/";
  const perms = getPermissions();
  for (const [perm, path] of HOME_FALLBACKS) {
    if (perm === "stats" && perms.includes("stats")) return "/";
    if (perm !== "stats" && perms.includes(perm)) return path;
  }
  return "/login";
}

function HomeRoute() {
  const r = getRole();
  if (!hasValidSession()) return <Navigate to="/login" replace />;
  if (r === "superuser") return <Dashboard />;
  if (r === "worker") {
    if (hasPermission("stats")) return <Dashboard />;
    const fallback = firstAllowedPath();
    if (fallback === "/") return <Dashboard />;
    return <Navigate to={fallback} replace />;
  }
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
              <PermissionRoute permission="photos">
                <Photos />
              </PermissionRoute>
            }
          />
          <Route
            path="/photo-ratings"
            element={
              <PermissionRoute permission="photos">
                <PhotoRatings />
              </PermissionRoute>
            }
          />
          <Route
            path="/tags"
            element={
              <PermissionRoute permission="photos">
                <Tags />
              </PermissionRoute>
            }
          />
          <Route
            path="/tagging"
            element={
              <PermissionRoute permission="photos">
                <Tagging />
              </PermissionRoute>
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
              <PermissionRoute permission="clients">
                <FittingRequests />
              </PermissionRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <PermissionRoute permission="ads">
                <Campaigns />
              </PermissionRoute>
            }
          />
          <Route
            path="/promo-banners"
            element={
              <PermissionRoute permission="ads">
                <PromoBanners />
              </PermissionRoute>
            }
          />
          <Route
            path="/hero-banners"
            element={
              <PermissionRoute permission="ads">
                <HeroBanners />
              </PermissionRoute>
            }
          />
          <Route
            path="/home-v2-gender-cards"
            element={
              <PermissionRoute permission="ads">
                <HomeV2GenderCards />
              </PermissionRoute>
            }
          />
          <Route
            path="/push"
            element={
              <PermissionRoute permission="ads">
                <PushNotifications />
              </PermissionRoute>
            }
          />
          <Route
            path="/seasons"
            element={
              <PermissionRoute permission="product">
                <Seasons />
              </PermissionRoute>
            }
          />
          <Route
            path="/brands"
            element={
              <PermissionRoute permission="product">
                <Brands />
              </PermissionRoute>
            }
          />
          <Route
            path="/brand-orders"
            element={
              <PermissionRoute permission="product">
                <BrandOrders />
              </PermissionRoute>
            }
          />
          <Route
            path="/payments"
            element={
              <PermissionRoute permission="product">
                <Payments />
              </PermissionRoute>
            }
          />
          <Route
            path="/shipments"
            element={
              <PermissionRoute permission="product">
                <Shipments />
              </PermissionRoute>
            }
          />
          <Route
            path="/fx-rates"
            element={
              <PermissionRoute permission="product">
                <FxRates />
              </PermissionRoute>
            }
          />
          <Route
            path="/ai-ingest"
            element={
              <PermissionRoute permission="photos">
                <AiIngest />
              </PermissionRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
