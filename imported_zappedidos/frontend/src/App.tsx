import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import PaymentPage from "@/pages/PaymentPage";
import StoreDetail from "@/pages/StoreDetail";
import Simulator from "@/pages/Simulator";
import WhatsAppConnect from "@/pages/WhatsAppConnect";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Home />} />
        <Route path="/lojas/:id" element={<StoreDetail />} />
        <Route path="/simulador" element={<Simulator />} />
        <Route path="/pagamento/:id" element={<PaymentPage />} />
        <Route path="/whatsapp" element={<WhatsAppConnect />} />
      </Routes>
      <Toaster position="bottom-right" richColors />
    </>
  );
}
