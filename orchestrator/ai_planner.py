import json
import os
from typing import Any

from openai import OpenAI

from .models import ExecutionPlan, PlanRequest, PlanStep
from .policy import approval_required, validate_plan
from .registry import workflows

SYSTEM_PROMPT = """You are a production infrastructure workflow planner. Select only registered workflow capabilities. Never invent workflow names, repositories, workflow files, inputs, outputs, or dependencies. Build the smallest safe sequence that satisfies the request. Prefer plan/validation before mutation. Return JSON only with: steps, where each step has workflow, reason, inputs, risk. Risk must be copied from the registry. Do not execute anything."""


def _registry_context() -> str:
    return json.dumps(workflows(), sort_keys=True)


def _fallback(req: PlanRequest) -> ExecutionPlan:
    text = req.request.lower()
    names = ["terraform_plan"]
    if any(word in text for word in ("upgrade", "rhel", "migration", "reprovision", "provision")):
        names = ["terraform_plan", "backup_server", "provision_server", "configure_tomcat", "validate_application"]
    steps: list[PlanStep] = []
    for index, name in enumerate(names, 1):
        cfg = workflows()[name]
        inputs: dict[str, Any] = {"application": req.application, "environment": req.environment}
        if name in {"configure_tomcat", "validate_application"}:
            inputs = {"instance_id": "${provision_server.instance_id}"}
        steps.append(PlanStep(step=index, workflow=name, reason=cfg["description"], inputs=inputs, risk=cfg["risk"]))
    return _validate(req, steps)


def _validate(req: PlanRequest, steps: list[PlanStep]) -> ExecutionPlan:
    plan = ExecutionPlan(request=req.request, application=req.application, environment=req.environment, steps=steps, approval_required=False)
    raw = plan.model_dump()
    raw["branch"] = "main"
    validate_plan(raw)
    plan.approval_required = approval_required(raw)
    return plan


def build_ai_plan(req: PlanRequest) -> ExecutionPlan:
    if not os.getenv("OPENAI_API_KEY"):
        return _fallback(req)
    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-5.6")
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=f"Registry:\n{_registry_context()}\n\nRequest:\n{req.request}\nApplication: {req.application}\nEnvironment: {req.environment}",
    )
    try:
        payload = json.loads(response.output_text)
        steps = [PlanStep(step=i, **step) for i, step in enumerate(payload["steps"], 1)]
        return _validate(req, steps)
    except Exception:
        return _fallback(req)
