import { cn } from "@/lib/utils";
import { InputHTMLAttributes } from "react";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn("h-10 w-full rounded-md border bg-white px-3 text-sm outline-none ring-primary/30 focus:ring", props.className)} />;
}
