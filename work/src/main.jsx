import React from "react";
import ReactDOM from "react-dom/client";
import { assertAppIdentity } from "./utils/assertAppIdentity.js";
import App from "./App.jsx";
import "../../shared/staff-ui.css";
import "./App.css";

if ("serviceWorker" in navigator) {
  const hadController = Boolean(navigator.serviceWorker.controller);
  let reloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloaded) return;
    reloaded = true;
    window.location.reload();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    void navigator.serviceWorker.getRegistration().then((r) => r?.update());
  });
}

if (assertAppIdentity()) {
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
