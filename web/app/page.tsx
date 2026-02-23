"use client";

import Link from "next/link";
import { patients } from "@/lib/mock-data";
import { Input } from "@/components/ui/input";
import { useMemo, useState } from "react";
import { StatusPill } from "@/components/StatusPill";

export default function HomePage() {
  const [q, setQ] = useState("");
  const [risk, setRisk] = useState("all");

  const rows = useMemo(() => patients.filter((p) => {
    const query = `${p.id} ${p.name} ${p.diagnosis}`.toLowerCase().includes(q.toLowerCase());
    const riskOk = risk === "all" || p.risk === risk;
    return query && riskOk;
  }), [q, risk]);

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-6">
      <header className="panel p-5">
        <h1 className="text-2xl font-semibold">Patient Registry</h1>
        <p className="text-sm text-slate-600">Search and filter monitored cardiology population.</p>
      </header>

      <section className="panel p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Input aria-label="Search patients" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, ID, diagnosis" />
          <select aria-label="Risk filter" className="h-10 rounded-md border bg-white px-3" value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="all">All risk levels</option>
            <option value="stable">Stable</option>
            <option value="moderate">Moderate</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left">Patient</th><th className="px-4 py-3 text-left">Diagnosis</th><th className="px-4 py-3 text-left">Risk</th><th className="px-4 py-3 text-left">Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className="border-t hover:bg-slate-50">
                <td className="px-4 py-3"><Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/patients/${p.id}`}>{p.name} ({p.id})</Link></td>
                <td className="px-4 py-3">{p.diagnosis}</td>
                <td className="px-4 py-3"><StatusPill risk={p.risk} /></td>
                <td className="px-4 py-3">{p.lastSeen}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="p-6 text-center text-sm text-slate-500">No patients match current filters.</div>}
      </section>
    </main>
  );
}
