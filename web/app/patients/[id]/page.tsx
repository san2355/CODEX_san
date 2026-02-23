"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { patients } from "@/lib/mock-data";
import { PatientHeader } from "@/components/PatientHeader";
import { MetricCard } from "@/components/MetricCard";
import { RecommendationCard } from "@/components/RecommendationCard";
import { ChartPanel } from "@/components/ChartPanel";
import { DataTable } from "@/components/DataTable";
import { VisitDetailDrawer } from "@/components/VisitDetailDrawer";
import { Visit } from "@/lib/types";

const tabs = ["Overview", "Vitals", "Labs", "Meds", "Plan"] as const;

export default function PatientDetailPage() {
  const params = useParams<{ id: string }>();
  const patient = useMemo(() => patients.find((p) => p.id === params.id), [params.id]);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("Overview");
  const [activeVisit, setActiveVisit] = useState<Visit | null>(null);

  if (!patient) return notFound();

  const latest = patient.visits[0];

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-6">
      <Link href="/" className="text-sm text-primary underline-offset-4 hover:underline">← Back to patient list</Link>
      <PatientHeader patient={patient} />

      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard label="SBP/DBP" value={`${latest.sbp}/${latest.dbp} mmHg`} subtext="Latest visit" />
        <MetricCard label="Heart Rate" value={`${latest.hr} bpm`} subtext="Target 60-100" />
        <MetricCard label="eGFR" value={`${latest.gfr}`} subtext="mL/min/1.73m²" />
        <MetricCard label="Potassium" value={`${latest.potassium.toFixed(1)} mmol/L`} />
      </section>

      <nav className="panel flex flex-wrap gap-2 p-2" aria-label="Dashboard tabs">
        {tabs.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`rounded-md px-3 py-2 text-sm ${activeTab === tab ? "bg-primary text-white" : "bg-white"}`}>
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Overview" && (
        <section className="grid gap-4 lg:grid-cols-2">
          <ChartPanel title="SBP Trend" data={patient.homeSeries} metric="sbp" targetLow={90} targetHigh={120} yLabel="mmHg" />
          <ChartPanel title="Heart Rate Trend" data={patient.homeSeries} metric="hr" targetLow={60} targetHigh={100} yLabel="bpm" />
          <ChartPanel title="GFR Trend" data={patient.homeSeries} metric="gfr" yLabel="mL/min" />
          <ChartPanel title="Potassium Trend" data={patient.homeSeries} metric="potassium" yLabel="mmol/L" />
        </section>
      )}

      {activeTab === "Vitals" && <DataTable data={patient.visits} onRowClick={setActiveVisit} />}

      {activeTab === "Labs" && (
        <section className="grid gap-3 md:grid-cols-2">
          <ChartPanel title="GFR Longitudinal" data={patient.homeSeries} metric="gfr" yLabel="mL/min" />
          <ChartPanel title="Potassium Longitudinal" data={patient.homeSeries} metric="potassium" yLabel="mmol/L" />
        </section>
      )}

      {activeTab === "Meds" && (
        <section className="panel p-4 text-sm text-slate-700">
          Current meds include ACE inhibitor, beta-blocker, and diuretic regimen. Use Plan tab for titration strategy.
        </section>
      )}

      {activeTab === "Plan" && (
        <section className="grid gap-3">
          {patient.recommendations.map((r) => <RecommendationCard key={r.sequence} recommendation={r} />)}
        </section>
      )}

      <VisitDetailDrawer visit={activeVisit} onClose={() => setActiveVisit(null)} />
    </main>
  );
}
