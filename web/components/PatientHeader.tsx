import { Patient } from "@/lib/types";
import { StatusPill } from "@/components/StatusPill";

export function PatientHeader({ patient }: { patient: Patient }) {
  return (
    <header className="panel p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{patient.name}</h1>
          <p className="mt-1 text-sm text-slate-600">{patient.id} • DOB {patient.dob} • {patient.diagnosis}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill risk={patient.risk} />
          <span className="rounded-md border bg-slate-50 px-2 py-1 text-xs">{patient.status}</span>
        </div>
      </div>
    </header>
  );
}
