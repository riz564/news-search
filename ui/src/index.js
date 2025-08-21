import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import NewSearchApp from "./NewSearchApp";

const root = createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <NewSearchApp />
  </React.StrictMode>
);
