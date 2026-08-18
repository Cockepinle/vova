import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

interface SectionHeaderProps {
  title: string;
  linkLabel: string;
}

export function SectionHeader({ title, linkLabel }: SectionHeaderProps) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      <Link to="/catalog">
        {linkLabel}
        <ChevronRight size={18} />
      </Link>
    </div>
  );
}
