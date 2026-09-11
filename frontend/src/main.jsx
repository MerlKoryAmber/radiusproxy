import React from "react";
import { createRoot } from "react-dom/client";
// Inter, self-hosted (bundled) — NO external CDN. The panel runs on locked-down
// networks (outbound stays local), so a render-blocking Google Fonts <link>
// stalled every page load. @fontsource ships the woff2 into our own bundle.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
