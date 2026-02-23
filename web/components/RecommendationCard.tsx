import { Recommendation } from "@/lib/types";
import { Card } from "@/components/ui/card";

export function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-semibold text-slate-500">SEQUENCE {recommendation.sequence}</p>
      <h3 className="mt-1 text-base font-semibold">{recommendation.title}</h3>
      <p className="mt-2 text-sm"><span className="font-medium">Titration:</span> {recommendation.titration}</p>
      <p className="mt-1 text-sm text-slate-600"><span className="font-medium text-slate-800">Rationale:</span> {recommendation.rationale}</p>
    </Card>
  );
}
