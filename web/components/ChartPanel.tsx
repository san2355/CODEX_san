"use client";

import { SeriesPoint } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface Props {
  title: string;
  data: SeriesPoint[];
  metric: keyof Pick<SeriesPoint, "sbp" | "hr" | "gfr" | "potassium">;
  targetLow?: number;
  targetHigh?: number;
  yLabel: string;
}

export function ChartPanel({ title, data, metric, targetLow, targetHigh, yLabel }: Props) {
  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      <div className="h-64" aria-label={`${title}-chart`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#d5dfeb" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} label={{ value: yLabel, angle: -90, position: "insideLeft" }} />
            <Tooltip />
            {targetLow !== undefined && <ReferenceLine y={targetLow} stroke="#2f5d96" strokeDasharray="4 4" />}
            {targetHigh !== undefined && <ReferenceLine y={targetHigh} stroke="#2f5d96" strokeDasharray="4 4" />}
            <Line type="monotone" dataKey={metric} stroke="#1e5b95" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
