import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AngleSelectorProps {
  angle: number;
  onAngleChange: (angle: number) => void;
  className?: string;
}

const ANGLE_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70];

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
