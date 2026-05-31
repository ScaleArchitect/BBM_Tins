import { ApiHealth } from "@/components/ApiHealth";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-wide text-brand-secondary">
          BBI Consultancy
        </p>
        <h1 className="mt-1 text-3xl font-bold text-brand-primary">
          TIN Collection Portal
        </h1>
        <p className="mt-3 text-slate-600">
          White-label B2B portal for collecting UAE VAT &amp; Corporate Tax
          certificate data. This is the Sprint&nbsp;0 skeleton — the technical
          spine is in place; business features arrive in later sprints.
        </p>
        <div className="mt-6">
          <ApiHealth />
        </div>
      </div>
    </main>
  );
}
