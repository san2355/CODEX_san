"use client";

import { Visit } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

export function VisitDetailDrawer({ visit, onClose }: { visit: Visit | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {visit && (
        <>
          <motion.div className="fixed inset-0 z-40 bg-black/30" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            role="dialog"
            aria-label="Visit detail drawer"
            className="fixed right-0 top-0 z-50 h-full w-full max-w-xl border-l bg-white p-6 shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 220, damping: 28 }}
          >
            <h3 className="text-lg font-semibold">Visit {visit.id}</h3>
            <p className="text-sm text-slate-500">{visit.date}</p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>SBP: {visit.sbp}</div><div>DBP: {visit.dbp}</div><div>HR: {visit.hr}</div><div>GFR: {visit.gfr}</div><div>K: {visit.potassium}</div>
            </div>
            <p className="mt-4 text-sm">{visit.note}</p>
            <h4 className="mt-4 font-semibold">Rules Triggered</h4>
            <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
              {visit.triggeredRules.map((rule) => <li key={rule}>{rule}</li>)}
            </ul>
            <button onClick={onClose} className="mt-6 rounded-md border px-3 py-2 text-sm">Close</button>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
