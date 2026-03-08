import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ANGLE_OPTIONS } from "@/lib/climbs";

interface AngleSelectorProps {
  angle: number;
  onAngleChange: (angle: number) => void;
  className?: string;
}

export default function AngleSelector({
  angle,
  onAngleChange,
  className = "",
}: AngleSelectorProps) {
  const handleValueChange = (value: string) => {
    onAngleChange(Number(value));
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <label htmlFor="angle-select" className="text-sm font-medium">
        Angle:
      </label>
      <Select value={angle.toString()} onValueChange={handleValueChange}>
        <SelectTrigger className="w-20">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ANGLE_OPTIONS.map((angleOption) => (
            <SelectItem key={angleOption} value={angleOption.toString()}>
              {angleOption}°
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
