import { useState, type ReactNode } from "react";
import { ArrowLeft, CircleHelp, House, Info, Menu, Mountain, Settings2 } from "lucide-react";
import { Link } from "react-router-dom";
import BrandWordmark from "@/components/BrandWordmark";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface MobilePageHeaderAction {
  label: string;
  icon?: ReactNode;
  onSelect?: () => void;
  to?: string;
  variant?: "default" | "secondary" | "outline" | "ghost";
}

interface MobilePageHeaderProps {
  title: string;
  backTo?: string;
  backLabel?: string;
  showBrand?: boolean;
  primaryAction?: MobilePageHeaderAction;
  onHelp?: () => void;
  menuGuideId?: string;
  className?: string;
}

function MobileMenuLink({
  icon,
  label,
  onSelect,
  to,
}: {
  icon: ReactNode;
  label: string;
  onSelect: () => void;
  to?: string;
}) {
  if (to) {
    return (
      <Button asChild variant="outline" className="w-full justify-between">
        <Link to={to} onClick={onSelect}>
          <span className="inline-flex items-center gap-2">
            {icon}
            <span>{label}</span>
          </span>
        </Link>
      </Button>
    );
  }

  return (
    <Button type="button" variant="outline" className="w-full justify-between" onClick={onSelect}>
      <span className="inline-flex items-center gap-2">
        {icon}
        <span>{label}</span>
      </span>
    </Button>
  );
}

export default function MobilePageHeader({
  title,
  backTo,
  backLabel = "Back",
  showBrand = false,
  primaryAction,
  onHelp,
  menuGuideId,
  className,
}: MobilePageHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const handleMenuAction = (action?: () => void) => {
    setMenuOpen(false);
    action?.();
  };

  const headerAction = primaryAction ? (
    primaryAction.to ? (
      <Button asChild size="sm" variant={primaryAction.variant ?? "outline"} className="h-9">
        <Link to={primaryAction.to}>
          {primaryAction.icon}
          <span>{primaryAction.label}</span>
        </Link>
      </Button>
    ) : (
      <Button
        type="button"
        size="sm"
        variant={primaryAction.variant ?? "outline"}
        className="h-9"
        onClick={primaryAction.onSelect}
      >
        {primaryAction.icon}
        <span>{primaryAction.label}</span>
      </Button>
    )
  ) : null;

  return (
    <>
      <header
        className={cn(
          "md:hidden rounded-2xl border bg-white/92 px-3 py-3 shadow-sm backdrop-blur",
          className
        )}
      >
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            {backTo ? (
              <Button asChild variant="ghost" className="-ml-2 h-9 px-2.5">
                <Link to={backTo}>
                  <ArrowLeft className="h-4 w-4" />
                  <span>{backLabel}</span>
                </Link>
              </Button>
            ) : showBrand ? (
              <Link to="/" aria-label="Back to home page" className="inline-flex max-w-full">
                <BrandWordmark imageClassName="h-[28px]" />
              </Link>
            ) : (
              <p className="truncate text-sm font-medium text-muted-foreground">{title}</p>
            )}
          </div>
          {headerAction}
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-9 w-9 shrink-0"
            aria-label={`Open ${title} menu`}
            data-guide={menuGuideId}
            onClick={() => setMenuOpen(true)}
          >
            <Menu className="h-4 w-4" />
          </Button>
        </div>
        {(showBrand || backTo) && (
          <div className="mt-2 min-w-0">
            <p className="truncate text-sm font-medium tracking-tight text-slate-900">{title}</p>
          </div>
        )}
      </header>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="right" className="w-[min(85vw,22rem)] p-0">
          <SheetHeader className="border-b px-5 py-5 text-left">
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>Quick links for this screen.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-3 px-5 py-5">
            {onHelp ? (
              <MobileMenuLink
                icon={<CircleHelp className="h-4 w-4" />}
                label="Help"
                onSelect={() => handleMenuAction(onHelp)}
              />
            ) : null}
            <MobileMenuLink
              icon={<House className="h-4 w-4" />}
              label="Community mode"
              to="/"
              onSelect={() => setMenuOpen(false)}
            />
            <MobileMenuLink
              icon={<Mountain className="h-4 w-4" />}
              label="Solo browse"
              to="/solo"
              onSelect={() => setMenuOpen(false)}
            />
            <MobileMenuLink
              icon={<Info className="h-4 w-4" />}
              label="About"
              to="/about"
              onSelect={() => setMenuOpen(false)}
            />
            <MobileMenuLink
              icon={<Settings2 className="h-4 w-4" />}
              label="Settings"
              to="/settings"
              onSelect={() => setMenuOpen(false)}
            />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
