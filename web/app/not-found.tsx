import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="panel p-8 text-center">
        <h1 className="text-xl font-semibold">Patient record not found</h1>
        <p className="mt-2 text-sm text-slate-600">The requested patient could not be found in the mock dataset.</p>
        <Link href="/" className="mt-4 inline-block text-primary underline">Return to patient list</Link>
      </div>
    </main>
  );
}
