import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const headerNavActionClassName =
  "highlight-link-parent h-auto rounded-full px-3 py-2 text-sm font-medium text-foreground shadow-none hover:bg-transparent hover:text-foreground active:bg-transparent dark:hover:bg-transparent";

export function HeaderNavButton({
  children,
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
}) {
  return (
    <Button
      type={type}
      variant="ghost"
      className={cn(headerNavActionClassName, className)}
      {...props}
    >
      <span className="highlight-link">{children}</span>
    </Button>
  );
}

export function HeaderNavLink({
  children,
  className,
  ...props
}: LinkProps & {
  children: ReactNode;
}) {
  return (
    <Button asChild variant="ghost" className={cn(headerNavActionClassName, className)}>
      <Link {...props}>
        <span className="highlight-link">{children}</span>
      </Link>
    </Button>
  );
}
