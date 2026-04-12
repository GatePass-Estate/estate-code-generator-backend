from fastapi import APIRouter

from app.domain.scopes import AnalysisScope
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.pipeline.orchestrator import AnomalyOrchestrator

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_visit_anomalies(body: AnalyzeRequest) -> AnalyzeResponse:
    orch = AnomalyOrchestrator()
    result = await orch.analyze(
        raw_records=body.raw_visit_records,
        scopes=body.scopes,
        context=body.context,
    )
    return AnalyzeResponse(**result)


@router.get("/scopes")
async def list_scopes() -> dict[str, list[str]]:
    return {"scopes": [s.value for s in AnalysisScope]}
