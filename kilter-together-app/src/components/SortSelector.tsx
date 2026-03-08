import type { ClimbSort } from "@/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SortSelectorProps {
  sort: ClimbSort;
  onSortChange: (sort: ClimbSort) => void;
  className?: string;
}

export default function SortSelector({
  sort,
  onSortChange,
  className = "",
}: SortSelectorProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <label htmlFor="sort-select" className="text-sm font-medium">
        Sort:
      </label>
      <Select
        value={sort}
        onValueChange={(value) => onSortChange(value as ClimbSort)}
      >
        <SelectTrigger className="w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="popular">Popular</SelectItem>
          <SelectItem value="newest">Newest</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
