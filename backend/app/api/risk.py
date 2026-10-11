from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.risk import RiskAnalyzeRequest, RiskReportOut
from app.services.risk import analyze

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/analyze", response_model=RiskReportOut)
async def analyze_text(
    data: RiskAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> RiskReportOut:
    return RiskReportOut.from_report(analyze(data.text))