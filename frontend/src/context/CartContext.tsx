import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Product } from "../types/product";

interface CartItem {
  product: Product;
  quantity: number;
}

interface CartContextValue {
  items: CartItem[];
  totalItems: number;
  addToCart: (product: Product, quantity: number) => void;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

const storageKey = "pakline-cart";

const readStoredCart = (): CartItem[] => {
  try {
    const stored = localStorage.getItem(storageKey);
    return stored ? (JSON.parse(stored) as CartItem[]) : [];
  } catch {
    return [];
  }
};

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(readStoredCart);

  const addToCart = (product: Product, quantity: number) => {
    setItems((current) => {
      const existing = current.find((item) => item.product.id === product.id);
      const next = existing
        ? current.map((item) =>
            item.product.id === product.id
              ? { ...item, quantity: item.quantity + quantity }
              : item,
          )
        : [...current, { product, quantity }];

      localStorage.setItem(storageKey, JSON.stringify(next));
      return next;
    });
  };

  const value = useMemo(
    () => ({
      items,
      totalItems: items.reduce((sum, item) => sum + item.quantity, 0),
      addToCart,
    }),
    [items],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export const useCart = () => {
  const context = useContext(CartContext);

  if (!context) {
    throw new Error("useCart must be used inside CartProvider");
  }

  return context;
};
