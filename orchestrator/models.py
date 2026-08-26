from typing import Any, Literal
from pydantic import BaseModel, Field

class PlanRequest(BaseModel):
    request: str = Field(min_length=3)
    application: str
    environment: Literal["dev", "test", "prod"]
    context: dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    step: int
    workflow: str
    reason: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    risk: str

class ExecutionPlan(BaseModel):
    request: str
    application: str
    environment: str
    steps: list[PlanStep]
    approval_required: bool

class Orchestration(BaseModel):
    id: str
    request: str
    application: str
    environment: str
    status: str
    plan: ExecutionPlan
    current_step: int = 0
    runs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
