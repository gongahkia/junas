import type { Climb, ClimbSort, GradeInfo } from "@/types";

export const ANGLE_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70] as const;
export const DEFAULT_ANGLE = 40;
export const DEFAULT_SORT: ClimbSort = "popular";

export function normalizeAngle(value?: string | null): number {
  const parsedValue = Number(value);
  return ANGLE_OPTIONS.includes(parsedValue as (typeof ANGLE_OPTIONS)[number])
    ? parsedValue
    : DEFAULT_ANGLE;
}

export function normalizeSort(value?: string | null): ClimbSort {
  return value === "newest" ? "newest" : DEFAULT_SORT;
}

export function getGradeInfoForAngle(
  climb: Climb,
  angle: number
): GradeInfo | undefined {
  return climb.grades?.[angle.toString()];
}

export function getGradeForAngle(climb: Climb, angle: number): string {
  return getGradeInfoForAngle(climb, angle)?.boulder || "N/A";
}

export function getRouteGradeForAngle(climb: Climb, angle: number): string {
  return getGradeInfoForAngle(climb, angle)?.route || "N/A";
}

export function formatClimbDate(value?: string): string {
  if (!value) {
    return "Unknown";
  }

  const parsedDate = new Date(value.replace(" ", "T") + "Z");
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return parsedDate.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
