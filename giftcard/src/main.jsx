import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { assertAppIdentity } from "./utils/assertAppIdentity.js";
import App from "./App.jsx";
import "../../shared/staff-ui.css";
import "./desktop.css";

if (assertAppIdentity()) {
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  );
}
