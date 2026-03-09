import { cn } from "@/lib/utils";

const kilterWordmarkSrc = `${import.meta.env.BASE_URL}branding/kilter.png`;
const togetherWordmarkSrc = `${import.meta.env.BASE_URL}branding/together.png`;

interface BrandWordmarkProps {
  className?: string;
  imageClassName?: string;
}

export default function BrandWordmark({ className, imageClassName }: BrandWordmarkProps) {
  return (
    <span
      className={cn(
        "brand-wordmark inline-flex max-w-full flex-wrap items-end gap-x-1 gap-y-1",
        className
      )}
    >
      <span className="brand-wordmark__piece brand-wordmark__piece--kilter">
        <img
          src={kilterWordmarkSrc}
          alt=""
          aria-hidden="true"
          className={cn("h-[50px] w-auto shrink-0 object-contain", imageClassName)}
        />
      </span>
      <span className="brand-wordmark__piece brand-wordmark__piece--together">
        <img
          src={togetherWordmarkSrc}
          alt=""
          aria-hidden="true"
          className={cn("h-[50px] w-auto shrink-0 object-contain", imageClassName)}
        />
      </span>
      <span className="sr-only">Kilter Together</span>
    </span>
  );
}
