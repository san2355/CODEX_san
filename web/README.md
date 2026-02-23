# EMR Web Prototype (Next.js 14)

Hospital-grade UI scaffold using:
- Next.js App Router + TypeScript
- TailwindCSS + shadcn-style primitives
- TanStack Table
- Recharts
- Framer Motion

## Run locally

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Included screens
- Patient list with search + risk filters
- Patient detail dashboard with tabs (Overview / Vitals / Labs / Meds / Plan)
- Visit detail drawer with raw values + triggered rules

## Data source
Uses mock data in `lib/mock-data.ts` mapped from planned visit/home-series style structures.
