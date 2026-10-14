import { CheckCircle, XCircle, AlertTriangle, Shield, Info } from "lucide-react";
import type { ReactNode } from "react";

type Variant = "success" | "danger" | "warning" | "mnpi" | "info" | "neutral";

interface Props {
  variant: Variant;
  children: ReactNode;
  className?: string;
}

const styles: Record<Variant, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  danger: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  mnpi: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  neutral: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

const icons: Record<Variant, ReactNode> = {
  success: <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />,
  danger: <XCircle className="w-3.5 h-3.5" aria-hidden="true" />,
  warning: <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />,
  mnpi: <Shield className="w-3.5 h-3.5" aria-hidden="true" />,
  info: <Info className="w-3.5 h-3.5" aria-hidden="true" />,
  neutral: <Info className="w-3.5 h-3.5" aria-hidden="true" />,
};

export function Badge({ variant, children, className = "" }: Props) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${styles[variant]} ${className}`}>
      {icons[variant]}
      {children}
    </span>
  );
}
