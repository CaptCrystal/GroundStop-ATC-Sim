import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import CheckoutSuccess from "./pages/CheckoutSuccess";
import Docs from "./pages/Docs";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/checkout-success" element={<CheckoutSuccess />} />
        <Route path="/docs" element={<Docs />} />
      </Routes>
    </BrowserRouter>
  );
}
