import { categories, products } from "../data/catalog";

export const getCategories = () => categories;

export const getCategoryById = (categoryId: string | undefined) =>
  categories.find((category) => category.id === categoryId);

export const getProducts = () => products;

export const getProductsByCategoryId = (categoryId: string | undefined) => {
  const category = getCategoryById(categoryId);

  if (!category) {
    return products;
  }

  return products.filter((product) => product.category === category.name);
};

export const getHitProducts = () => products.filter((product) => product.isHit);

export const getProductById = (productId: string | undefined) =>
  products.find((product) => product.id === productId);
