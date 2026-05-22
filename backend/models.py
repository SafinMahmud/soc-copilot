from pydantic import BaseModel
from typing import Optional, List


class QueryRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    time_range: str = "-24h"


class SPLResult(BaseModel):
    spl: str
    results: List[dict]
    result_count: int
    error: Optional[str] = None


class InvestigateRequest(BaseModel):
    entity: str
    entity_type: str
    time_range: str = "-24h"


class MitreTechnique(BaseModel):
    technique_id: str
    name: str
    tactic: str
    description: str


class TimelineEvent(BaseModel):
    timestamp: str
    event_type: str
    description: str
    raw_log: str
    severity: str


class RemediationStep(BaseModel):
    priority: str
    action: str
    rationale: str


class InvestigationReport(BaseModel):
    entity: str
    entity_type: str
    severity: str
    severity_rationale: str
    summary: str
    timeline: List[TimelineEvent]
    mitre_techniques: List[MitreTechnique]
    remediation_steps: List[RemediationStep]
    queries_run: List[str]
    raw_findings: dict
