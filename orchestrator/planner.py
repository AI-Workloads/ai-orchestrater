from .ai_planner import build_ai_plan
from .models import ExecutionPlan, PlanRequest


def build_plan(req: PlanRequest) -> ExecutionPlan:
    return build_ai_plan(req)
