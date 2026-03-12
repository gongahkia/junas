import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface HeaderNavRailItem {
  label: string;
  icon: LucideIcon;
  to?: string;
  onClick?: () => void;
  dataGuide?: string;
}

interface HeaderNavRailProps {
  items: HeaderNavRailItem[];
  className?: string;
  label?: string;
}

export default function HeaderNavRail({
  items,
  className,
  label = "Page actions",
}: HeaderNavRailProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <nav
      aria-label={label}
      className={cn(
        "flex shrink-0 flex-col gap-1.5 rounded-[1.5rem] border border-white/70 bg-white/82 p-2 shadow-xl shadow-slate-950/8 backdrop-blur transition-[width] duration-200",
        expanded ? "w-52" : "w-14",
        className
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={expanded ? "Collapse menu" : "Expand menu"}
        className={cn(
          "h-10 rounded-xl text-foreground transition-[padding,justify-content] duration-200",
          expanded ? "justify-between px-3" : "justify-center px-0"
        )}
        onClick={() => setExpanded((current) => !current)}
      >
        <span
          className={cn(
            "overflow-hidden whitespace-nowrap text-sm font-medium transition-[max-width,opacity,margin] duration-200",
            expanded ? "mr-2 max-w-[8rem] opacity-100" : "mr-0 max-w-0 opacity-0"
          )}
          aria-hidden={!expanded}
        >
          Menu
        </span>
        {expanded ? <ChevronRight className="h-4 w-4 shrink-0" /> : <ChevronLeft className="h-4 w-4 shrink-0" />}
      </Button>

      <div className="flex flex-col gap-1">
        {items.map((item) => {
          const icon = <item.icon className="h-4 w-4 shrink-0" />;
          const labelText = (
            <span
              className={cn(
                "overflow-hidden whitespace-nowrap text-sm font-medium transition-[max-width,opacity,margin] duration-200",
                expanded ? "ml-2 max-w-[9rem] opacity-100" : "ml-0 max-w-0 opacity-0"
              )}
              aria-hidden={!expanded}
            >
              {item.label}
            </span>
          );

          if (item.to) {
            return (
              <Button
                key={item.label}
                asChild
                variant="ghost"
                size="sm"
                className={cn(
                  "h-10 rounded-xl text-foreground transition-[padding,justify-content] duration-200",
                  expanded ? "justify-start px-3" : "justify-center px-0"
                )}
              >
                <Link
                  to={item.to}
                  aria-label={item.label}
                  title={item.label}
                  data-guide={item.dataGuide}
                  onClick={item.onClick}
                >
                  {icon}
                  {labelText}
                </Link>
              </Button>
            );
          }

          return (
            <Button
              key={item.label}
              type="button"
              variant="ghost"
              size="sm"
              aria-label={item.label}
              title={item.label}
              data-guide={item.dataGuide}
              className={cn(
                "h-10 rounded-xl text-foreground transition-[padding,justify-content] duration-200",
                expanded ? "justify-start px-3" : "justify-center px-0"
              )}
              onClick={item.onClick}
            >
              {icon}
              {labelText}
            </Button>
          );
        })}
      </div>
    </nav>
  );
}
