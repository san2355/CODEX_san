import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <main className="mx-auto max-w-7xl p-6">
      <Skeleton className="mb-4 h-10 w-96" />
      <Skeleton className="h-24 w-full" />
    </main>
  );
}
