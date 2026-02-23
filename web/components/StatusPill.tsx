import { RiskLevel } from "@/lib/types";

const styles: Record<RiskLevel, string> = {
  stable: "bg-emerald-100 text-emerald-800",
  moderate: "bg-amber-100 text-amber-800",
  critical: "bg-rose-100 text-rose-800"
};

export function StatusPill({ risk }: { risk: RiskLevel }) {
  return (
    <span aria-label={`risk-${risk}`} className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${styles[risk]}`}>
      {risk}
    </span>
  );
}
