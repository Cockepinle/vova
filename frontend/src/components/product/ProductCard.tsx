import { Heart, Minus, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCart } from "../../context/CartContext";
import type { Product } from "../../types/product";

interface ProductCardProps {
  product: Product;
}

export function ProductCard({ product }: ProductCardProps) {
  const [quantity, setQuantity] = useState(product.minQuantity);
  const { addToCart } = useCart();
  const navigate = useNavigate();

  const openProduct = () => navigate(`/product/${product.id}`);

  return (
    <article
      className="product-card"
      onClick={openProduct}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openProduct();
        }
      }}
      role="link"
      tabIndex={0}
    >
      <div className="product-image">
        {product.isHit && <span className="hit-badge">ХИТ</span>}
        <button
          className="favorite-button"
          aria-label="Добавить в избранное"
          onClick={(event) => event.stopPropagation()}
        >
          <Heart size={20} />
        </button>
        <img src={product.images[0]} alt={product.name} />
      </div>
      <div className="product-info">
        <span className="product-sku">{product.sku}</span>
        <h3>{product.name}</h3>
        <div className="product-buy-row">
          <p className="price">
            {product.price.toLocaleString("ru-RU")} ₽ <span>/ {product.unit}</span>
          </p>
          <div className="quantity-control" aria-label="Количество">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setQuantity((value) => Math.max(product.minQuantity, value - 1));
              }}
              aria-label="Уменьшить количество"
            >
              <Minus size={16} />
            </button>
            <span>{quantity}</span>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setQuantity((value) => value + 1);
              }}
              aria-label="Увеличить количество"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>
        <button
          className="add-to-cart"
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            addToCart(product, quantity);
          }}
        >
          В корзину
        </button>
      </div>
    </article>
  );
}
