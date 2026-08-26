import json
import os
from typing import Any

from openai import OpenAI

from .models import ExecutionPlan, PlanRequest, PlanStep
from .policy import approval_required, validate_plan
from .registry import workflows

SYSTEM_PROMPT = """You are a production infrastructure workflow planner. Select only registered workflow capabilities. Never invent workflow names, repositories, workflow files, inputs, outputs, or dependencies. Build the smallest safe sequence that satisfies the request. For terraform_plan, choose exactly one action: plan for validation/read-only requests, apply for deployment/change requests, or destroy only when explicitly requested. Return JSON only with: steps, where each step has workflow, reason, inputs, risk. Do not execute anything."""


def _registry_context() -> str:
    return json.dumps(workflows(), sort_keys=True)


def _terraform_action(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("destroy", "delete", "decommission", "tear down")):
        return "destroy"
    if any(word in lowered for word in ("apply", "deploy", "provision", "create", "change", "upgrade", "reprovision", "migrate")):
        return "apply"
    return "plan"


def _workflow_environment(environment: str) -> str:
    return {"prod": "prd", "test": "uat"}.get(environment, environment)


def _terraform_step(req: PlanRequest, action: str) -> PlanStep:
    risk = {"plan": "low", "apply": "high", "destroy": "critical"}[action]
    return PlanStep(step=1, workflow="terraform_plan", reason=f"Run Terraform {action} for the requested infrastructure operation", inputs={"environment": _workflow_environment(req.environment), "action": action}, risk=risk)


def _fallback(req: PlanRequest) -> ExecutionPlan:
    text = req.request
    action = _terraform_action(text)
    names = ["terraform_plan"]
    if any(word in text.lower() for word in ("upgrade", "rhel", "migration", "reprovision")):
        names = ["terraform_plan", "backup_server", "provision_server", "configure_tomcat", "validate_application"]
    steps: list[PlanStep] = []
    for index, name in enumerate(names, 1):
        if name == "terraform_plan":
            step = _terraform_step(req, action)
            step.step = index
        else:
            cfg = workflows()[name]
            inputs: dict[str, Any] = {"application": req.application, "environment": req.environment}
            if name in {"configure_tomcat", "validate_application"}:
                inputs = {"instance_id": "${provision_server.instance_id}"}
            step = PlanStep(step=index, workflow=name, reason=cfg["description"], inputs=inputs, risk=cfg["risk"])
        steps.append(step)
    return _validate(req, steps)


def _validate(req: PlanRequest, steps: list[PlanStep]) -> ExecutionPlan:
    for step in steps:
        if step.workflow == "terraform_plan":
            action = step.inputs.get("action")
            expected = {"plan": "low", "apply": "high", "destroy": "critical"}.get(action)
            if expected:
                step.risk = expected
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
    response = client.responses.create(model=model, instructions=SYSTEM_PROMPT, input=f"Registry:\n{_registry_context()}\n\nRequest:\n{req.request}\nApplication: {req.application}\nEnvironment: {req.environment}")
    try:
        payload = json.loads(response.output_text)
        steps = [PlanStep(step=i, **step) for i, step in enumerate(payload["steps"], 1)]
        return _validate(req, steps)
    except Exception:
        return _fallback(req)
