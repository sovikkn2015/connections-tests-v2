import type { ReactNode, HTMLAttributes } from "react";

type Variant = "default" | "interactive" | "highlighted";

interface Props extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  children: ReactNode;
}

const variantStyles: Record<Variant, string> = {
  default: "bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700",
  interactive: "bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md cursor-pointer transition-all",
  highlighted: "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800",
};

export function Card({ variant = "default", children, className = "", ...rest }: Props) {
  return (
    <div className={`rounded-xl p-4 ${variantStyles[variant]} ${className}`} {...rest}>
      {children}
    </div>
  );
}
