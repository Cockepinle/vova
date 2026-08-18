import { BrowserRouter, Route, Routes } from "react-router-dom";
import { CartProvider } from "./context/CartContext";
import { Header } from "./components/layout/Header";
import { CatalogPage } from "./pages/CatalogPage";
import { HomePage } from "./pages/HomePage";
import { ProductPage } from "./pages/ProductPage";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <main className="placeholder-page">
      <h1>{title}</h1>
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <CartProvider>
        <Header />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/catalog/:categoryId" element={<CatalogPage />} />
          <Route path="/product/:productId" element={<ProductPage />} />
          <Route path="/team" element={<PlaceholderPage title="Команда" />} />
          <Route path="/contacts" element={<PlaceholderPage title="Контакты" />} />
        </Routes>
      </CartProvider>
    </BrowserRouter>
  );
}
