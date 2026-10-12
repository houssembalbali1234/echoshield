import type { RiskLevel, RiskReport } from "@/lib/types";

const LEVELS: Record<RiskLevel, { label: string; icon: string; className: string }> = {
  low: { label: "Risque faible", icon: "🟢", className: "bg-emerald-50 text-emerald-900 ring-emerald-200" },
  medium: { label: "Risque moyen", icon: "🟠", className: "bg-amber-50 text-amber-950 ring-amber-200" },
  high: { label: "Risque élevé", icon: "🔴", className: "bg-rose-50 text-rose-900 ring-rose-200" },
};

export function RiskPanel({ report }: { report: RiskReport }) {
  const level = LEVELS[report.level];

  return (
    <div className={`rounded-xl p-4 ring-1 ${level.className}`} role="status" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">
          <span aria-hidden>{level.icon}</span> {level.label}
        </p>
        <p className="text-xs opacity-80">Score {report.score} / 100</p>
      </div>
      <p className="mt-1 text-sm">{report.recommendation}</p>

      {report.signals.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {report.signals.map((signal) => (
            <li key={signal.code}>
              • {signal.label}
              {signal.matches.length > 0 && (
                <span className="opacity-75"> — « {signal.matches.join(" », « ")} »</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}