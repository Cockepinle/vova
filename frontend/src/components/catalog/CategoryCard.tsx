import { Link } from "react-router-dom";
import type { Category } from "../../types/product";

interface CategoryCardProps {
  category: Category;
}

export function CategoryCard({ category }: CategoryCardProps) {
  return (
    <Link className="category-card" to={`/catalog/${category.id}`}>
      <img src={category.image} alt="" />
      <span>{category.name}</span>
    </Link>
  );
}
