import type { Category, Product } from "../types/product";

export const warehouseImage =
  "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1800&q=80";

export const categories: Category[] = [
  {
    id: "corrugated-cardboard",
    name: "Гофрокартон",
    image:
      "https://images.unsplash.com/photo-1629802511683-30dcd09f689e?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "foam",
    name: "Пенопласт и поролон",
    image:
      "https://images.unsplash.com/photo-1494412519320-aa613dfb7738?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "stretch-film",
    name: "Стрейч-плёнка",
    image:
      "https://images.unsplash.com/photo-1558060370-d644479cb6f7?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "tape",
    name: "Скотч и клейкая лента",
    image:
      "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "warehouse",
    name: "Складская упаковка",
    image: warehouseImage,
  },
  {
    id: "kraft",
    name: "Крафт-упаковка",
    image:
      "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "office",
    name: "Офисная упаковка",
    image:
      "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=80",
  },
  {
    id: "tools",
    name: "Упаковочные инструменты",
    image:
      "https://images.unsplash.com/photo-1629802511683-30dcd09f689e?auto=format&fit=crop&w=900&q=80",
  },
];

export const products: Product[] = [
  {
    id: "gk-5l-600",
    name: "Гофрокороб Г-23, 5 слоёв",
    category: "Гофрокартон",
    subcategory: "Короба",
    description: "Плотный пятислойный короб для переезда, хранения и оптовой доставки.",
    price: 48,
    images: [categories[0].image],
    specifications: {
      Материал: "Пятислойный гофрокартон",
      Размер: "600 x 400 x 400 мм",
    },
    availability: "in-stock",
    sku: "GK-5L-600",
    minQuantity: 1,
    unit: "шт",
    isHit: true,
  },
  {
    id: "kr-70-100",
    name: "Крафт-бумага 70 г/м², 1 × 100 м",
    category: "Крафт-упаковка",
    subcategory: "Бумага",
    description: "Рулонная крафт-бумага для упаковки заказов и заполнения пустот.",
    price: 890,
    oldPrice: 1040,
    images: [categories[5].image],
    specifications: {
      Плотность: "70 г/м²",
      Намотка: "100 м",
    },
    availability: "in-stock",
    sku: "KR-70-100",
    minQuantity: 1,
    unit: "рул",
    isHit: true,
  },
  {
    id: "kvp-35-45",
    name: "Крафт-пакет с ручками 35 × 45",
    category: "Крафт-упаковка",
    subcategory: "Пакеты",
    description: "Бумажный пакет с усиленными ручками для розницы и доставки.",
    price: 18,
    images: [categories[5].image],
    specifications: {
      Размер: "350 x 450 мм",
      Цвет: "Бурый",
    },
    availability: "in-stock",
    sku: "KVP-35-45",
    minQuantity: 1,
    unit: "шт",
    isHit: true,
  },
];
