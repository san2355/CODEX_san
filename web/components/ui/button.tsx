import { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Button({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={cn("inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-white hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary/50", className)} />;
}
