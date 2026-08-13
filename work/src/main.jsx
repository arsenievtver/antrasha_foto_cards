import React from "react";
import ReactDOM from "react-dom/client";
import { assertAppIdentity } from "./utils/assertAppIdentity.js";
import App from "./App.jsx";
import "./App.css";

if (assertAppIdentity()) {
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
