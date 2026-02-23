export type RiskLevel = "stable" | "moderate" | "critical";

export interface Visit {
  id: string;
  date: string;
  sbp: number;
  dbp: number;
  hr: number;
  gfr: number;
  potassium: number;
  note: string;
  triggeredRules: string[];
}

export interface SeriesPoint {
  time: string;
  sbp: number;
  dbp: number;
  hr: number;
  gfr: number;
  potassium: number;
}

export interface Recommendation {
  sequence: number;
  title: string;
  titration: string;
  rationale: string;
}

export interface Patient {
  id: string;
  name: string;
  dob: string;
  diagnosis: string;
  risk: RiskLevel;
  status: "Active" | "Monitoring" | "Needs Review";
  lastSeen: string;
  visits: Visit[];
  homeSeries: SeriesPoint[];
  recommendations: Recommendation[];
}
