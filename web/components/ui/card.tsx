import { cn } from "@/lib/utils";
import { PropsWithChildren } from "react";

export function Card({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <section className={cn("panel", className)}>{children}</section>;
}
