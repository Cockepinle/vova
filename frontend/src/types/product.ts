export type ProductAvailability = "in-stock" | "preorder" | "out-of-stock";

export interface Product {
  id: string;
  name: string;
  category: string;
  subcategory: string;
  description: string;
  price: number;
  oldPrice?: number;
  images: string[];
  specifications: Record<string, string>;
  availability: ProductAvailability;
  sku: string;
  minQuantity: number;
  unit: string;
  isHit?: boolean;
}

export interface Category {
  id: string;
  name: string;
  image: string;
}
