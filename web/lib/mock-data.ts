import { Patient } from "@/lib/types";

const makeSeries = (seed: number) =>
  Array.from({ length: 24 }, (_, i) => ({
    time: `2026-02-${String(i + 1).padStart(2, "0")}`,
    sbp: 108 + ((i * 3 + seed) % 14),
    dbp: 64 + ((i * 2 + seed) % 12),
    hr: 62 + ((i * 5 + seed) % 20),
    gfr: 56 + ((i + seed) % 10),
    potassium: 4.1 + (((i + seed) % 5) * 0.08)
  }));

export const patients: Patient[] = [
  {
    id: "HF001",
    name: "Martha Glover",
    dob: "1958-06-12",
    diagnosis: "HFrEF with CKD stage 3",
    risk: "moderate",
    status: "Monitoring",
    lastSeen: "2026-02-22",
    homeSeries: makeSeries(2),
    visits: [
      {
        id: "V-HF001-1",
        date: "2026-02-22",
        sbp: 116,
        dbp: 76,
        hr: 88,
        gfr: 61,
        potassium: 4.4,
        note: "Improved BP profile after beta-blocker uptitration.",
        triggeredRules: ["HR > 85 moderate", "Weight gain trend +1.2kg/7d"]
      }
    ],
    recommendations: [
      { sequence: 1, title: "ACE inhibitor optimization", titration: "Increase lisinopril 10mg to 20mg daily", rationale: "Persistent elevated afterload profile with preserved renal tolerance." },
      { sequence: 2, title: "Diuretic monitoring", titration: "Maintain furosemide 40mg daily", rationale: "No edema progression; continue volume maintenance." }
    ]
  },
  {
    id: "HF002",
    name: "George Bell",
    dob: "1949-02-03",
    diagnosis: "HFpEF, hypertension",
    risk: "critical",
    status: "Needs Review",
    lastSeen: "2026-02-23",
    homeSeries: makeSeries(7),
    visits: [
      {
        id: "V-HF002-1",
        date: "2026-02-23",
        sbp: 139,
        dbp: 93,
        hr: 104,
        gfr: 54,
        potassium: 4.9,
        note: "Escalating BP and HR variability in prior week.",
        triggeredRules: ["SBP > 130 high", "HR > 100 high", "K > 4.8 warning"]
      }
    ],
    recommendations: [
      { sequence: 1, title: "Rate control intensification", titration: "Consider metoprolol increase 25mg -> 50mg", rationale: "Sustained HR above target with symptomatic episodes." }
    ]
  }
];
