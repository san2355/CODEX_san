import { Card } from "@/components/ui/card";

export function MetricCard({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      {subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}
    </Card>
  );
}
