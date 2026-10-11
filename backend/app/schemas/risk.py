from pydantic import BaseModel, Field

from app.services.risk import RiskLevel, RiskReport


class RiskAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class RiskSignalOut(BaseModel):
    code: str
    label: str
    weight: int
    matches: list[str]


class RiskReportOut(BaseModel):
    level: RiskLevel
    score: int
    signals: list[RiskSignalOut]
    recommendation: str

    @classmethod
    def from_report(cls, report: RiskReport) -> "RiskReportOut":
        return cls(
            level=report.level,
            score=report.score,
            signals=[
                RiskSignalOut(
                    code=signal.code,
                    label=signal.label,
                    weight=signal.weight,
                    matches=signal.matches,
                )
                for signal in report.signals
            ],
            recommendation=report.recommendation,
        )