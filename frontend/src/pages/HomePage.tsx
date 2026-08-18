import { ArrowRight, HelpCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { CategoryCard } from "../components/catalog/CategoryCard";
import { SectionHeader } from "../components/common/SectionHeader";
import { ProductCard } from "../components/product/ProductCard";
import { warehouseImage } from "../data/catalog";
import { getCategories, getHitProducts } from "../services/catalogService";

const stats = [
  { value: "300+", label: "SKU на складе" },
  { value: "12 лет", label: "На рынке" },
  { value: "2400+", label: "Клиентов" },
  { value: "День в день", label: "Отгрузка" },
];

export function HomePage() {
  const categories = getCategories();
  const hitProducts = getHitProducts();

  return (
    <>
      <section className="hero" style={{ backgroundImage: `url(${warehouseImage})` }}>
        <div className="hero-overlay" />
        <div className="hero-content">
          <p className="eyebrow">Оптовые поставки · Москва и Россия</p>
          <h1>Упаковка для вашего бизнеса</h1>
          <p className="hero-copy">
            Гофрокартон, стрейч-плёнка, скотч, пузырчатая плёнка и 300+ SKU на
            складе в Москве. Отгрузка в день заказа.
          </p>
          <div className="hero-actions">
            <Link className="primary-cta" to="/catalog">
              Смотреть каталог
              <ArrowRight size={22} />
            </Link>
            <Link className="secondary-cta" to="/contacts">
              Запросить КП
            </Link>
          </div>
        </div>
      </section>

      <section className="stats-band" aria-label="Показатели компании">
        {stats.map((stat) => (
          <div className="stat-item" key={stat.label}>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </div>
        ))}
      </section>

      <main>
        <section className="categories-section">
          <SectionHeader title="Категории" linkLabel="Весь каталог" />
          <div className="category-grid">
            {categories.map((category) => (
              <CategoryCard category={category} key={category.id} />
            ))}
          </div>
        </section>

        <section className="hits-section">
          <SectionHeader title="Хиты продаж" linkLabel="Смотреть все" />
          <div className="product-grid">
            {hitProducts.map((product) => (
              <ProductCard product={product} key={product.id} />
            ))}
          </div>
        </section>
      </main>

      <button className="help-button" aria-label="Помощь">
        <HelpCircle size={24} />
      </button>
    </>
  );
}
