import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { getProductById } from "../services/catalogService";

export function ProductPage() {
  const { productId } = useParams();
  const product = getProductById(productId);
  const { addToCart } = useCart();

  if (!product) {
    return (
      <main className="placeholder-page">
        <h1>Товар не найден</h1>
        <Link className="back-link" to="/catalog">
          <ArrowLeft size={18} />
          Вернуться в каталог
        </Link>
      </main>
    );
  }

  return (
    <main className="product-page">
      <Link className="back-link" to="/catalog">
        <ArrowLeft size={18} />
        Назад в каталог
      </Link>

      <section className="product-detail">
        <div className="product-gallery">
          <img src={product.images[0]} alt={product.name} />
        </div>

        <div className="product-detail-info">
          <span className="product-sku">{product.sku}</span>
          <h1>{product.name}</h1>
          <p>{product.description}</p>
          <p className="price">
            {product.price.toLocaleString("ru-RU")} ₽ <span>/ {product.unit}</span>
          </p>
          <button className="add-to-cart" type="button" onClick={() => addToCart(product, product.minQuantity)}>
            В корзину
          </button>
        </div>
      </section>

      <section className="specs-section">
        <h2>Характеристики</h2>
        <dl>
          {Object.entries(product.specifications).map(([name, value]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}
