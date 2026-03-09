import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface RoomFistBumpButtonProps {
  active: boolean;
  climbName: string;
  count: number;
  disabled?: boolean;
  onClick: () => void;
  className?: string;
}

export default function RoomFistBumpButton({
  active,
  climbName,
  count,
  disabled = false,
  onClick,
  className,
}: RoomFistBumpButtonProps) {
  const countLabel = `${count} ${count === 1 ? "fist bump" : "fist bumps"}`;

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      aria-label={`${active ? "Remove" : "Add"} fist bump for ${climbName}. ${countLabel}.`}
      aria-pressed={active}
      disabled={disabled}
      className={cn(
        "h-9 rounded-full border px-3 text-sm shadow-none",
        active
          ? "border-amber-300 bg-amber-100 text-amber-950 hover:bg-amber-100"
          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
        className
      )}
      onClick={onClick}
    >
      <span aria-hidden="true" className="text-base leading-none">
        👊
      </span>
      <span>{count}</span>
    </Button>
  );
}
