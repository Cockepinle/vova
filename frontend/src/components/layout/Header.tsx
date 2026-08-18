import { Heart, Search, ShoppingCart, UserRound } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useCart } from "../../context/CartContext";

const navItems = [
  { label: "Главная", href: "/" },
  { label: "Каталог", href: "/catalog" },
  { label: "Команда", href: "/team" },
  { label: "Контакты", href: "/contacts" },
];

export function Header() {
  const { totalItems } = useCart();

  return (
    <header className="site-header">
      <div className="header-inner">
        <NavLink className="brand" to="/" aria-label="PakLine">
          <span className="brand-mark">PL</span>
          <span className="brand-name">PakLine</span>
        </NavLink>

        <nav className="main-nav" aria-label="Главная навигация">
          {navItems.map((item) => (
            <NavLink key={item.href} to={item.href}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <label className="search-box">
          <Search size={18} strokeWidth={1.8} />
          <input placeholder="Поиск товаров..." />
        </label>

        <div className="header-actions">
          <button aria-label="Профиль">
            <UserRound size={20} strokeWidth={2} />
          </button>
          <button aria-label="Избранное">
            <Heart size={21} strokeWidth={2} />
          </button>
          <button className="cart-button" aria-label="Корзина">
            <ShoppingCart size={22} strokeWidth={2.2} />
            {totalItems > 0 && <span>{totalItems}</span>}
          </button>
        </div>
      </div>
    </header>
  );
}
