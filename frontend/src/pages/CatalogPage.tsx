import { Link, useParams } from "react-router-dom";
import { ProductCard } from "../components/product/ProductCard";
import { getCategories, getCategoryById, getProductsByCategoryId } from "../services/catalogService";

export function CatalogPage() {
  const { categoryId } = useParams();
  const categories = getCategories();
  const activeCategory = getCategoryById(categoryId);
  const products = getProductsByCategoryId(categoryId);

  return (
    <main className="catalog-page">
      <section className="catalog-heading">
        <p className="eyebrow">Каталог</p>
        <h1>{activeCategory ? activeCategory.name : "Все товары"}</h1>
      </section>

      <section className="catalog-layout">
        <aside className="catalog-sidebar" aria-label="Категории каталога">
          <Link className={!activeCategory ? "active" : undefined} to="/catalog">
            Все товары
          </Link>
          {categories.map((category) => (
            <Link
              className={category.id === activeCategory?.id ? "active" : undefined}
              key={category.id}
              to={`/catalog/${category.id}`}
            >
              {category.name}
            </Link>
          ))}
        </aside>

        <div className="catalog-results">
          {products.length > 0 ? (
            <div className="product-grid">
              {products.map((product) => (
                <ProductCard product={product} key={product.id} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <h2>Товары скоро появятся</h2>
              <p>В этой категории пока нет позиций, но каталог уже готов их показать.</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
