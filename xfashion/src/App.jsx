import { BrowserRouter, Route, Routes } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import BlogIndex from "./pages/BlogIndex.jsx";
import BlogArticle from "./pages/BlogArticle.jsx";
import { useAttribution } from "./utils/ref.js";

function AppRoutes() {
  useAttribution();
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/blog" element={<BlogIndex />} />
      <Route path="/blog/:slug" element={<BlogArticle />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
