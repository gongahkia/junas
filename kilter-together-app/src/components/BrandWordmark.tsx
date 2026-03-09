import { cn } from "@/lib/utils";

const kilterWordmarkSrc = `${import.meta.env.BASE_URL}branding/kilter.png`;
const togetherWordmarkSrc = `${import.meta.env.BASE_URL}branding/together.png`;

interface BrandWordmarkProps {
  className?: string;
  imageClassName?: string;
}

export default function BrandWordmark({ className, imageClassName }: BrandWordmarkProps) {
  return (
    <span className={cn("inline-flex max-w-full flex-wrap items-end gap-x-1 gap-y-1", className)}>
      <img
        src={kilterWordmarkSrc}
        alt=""
        aria-hidden="true"
        className={cn("h-[50px] w-auto shrink-0 object-contain", imageClassName)}
      />
      <img
        src={togetherWordmarkSrc}
        alt=""
        aria-hidden="true"
        className={cn("h-[50px] w-auto shrink-0 object-contain", imageClassName)}
      />
      <span className="sr-only">Kilter Together</span>
    </span>
  );
}
