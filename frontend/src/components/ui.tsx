import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Bouton
// ---------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "danger" | "success";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary: "bg-white text-slate-900 ring-1 ring-slate-300 hover:bg-slate-50",
  danger: "bg-rose-600 text-white hover:bg-rose-700",
  success: "bg-emerald-600 text-white hover:bg-emerald-700",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Champ de formulaire avec son libellé
// ---------------------------------------------------------------------------

export function Field({
  label,
  hint,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; id: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
        {...props}
      />
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Carte : un bloc blanc encadré
// ---------------------------------------------------------------------------

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message coloré : erreur, succès, avertissement, information
// ---------------------------------------------------------------------------

type Tone = "error" | "success" | "warning" | "info";

const TONES: Record<Tone, string> = {
  error: "bg-rose-50 text-rose-800 ring-rose-200",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  warning: "bg-amber-50 text-amber-900 ring-amber-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
};

export function Alert({ tone = "info", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-lg px-4 py-3 text-sm ring-1 ${TONES[tone]}`}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Logo
// ---------------------------------------------------------------------------

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight">
      <span aria-hidden className="grid size-8 place-items-center rounded-lg bg-indigo-600 text-white">
        🛡️
      </span>
      EchoShield
    </span>
  );
}