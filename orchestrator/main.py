import os
import uuid
from fastapi import FastAPI, HTTPException
from .models import PlanRequest, Orchestration
from .planner import build_plan
from .state import StateStore
from .registry import workflows, get_workflow
from .github_client import GitHubClient

app = FastAPI(title="AI GitHub Actions Orchestrator", version="0.1.0")
store = StateStore()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/workflows")
def list_workflows():
    return workflows()

@app.post("/plan")
def plan(req: PlanRequest):
    try:
        return build_plan(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/orchestrations")
def create(req: PlanRequest):
    try:
        execution_plan = build_plan(req)
        oid = f"ORCH-{uuid.uuid4().hex[:12].upper()}"
        status = "AWAITING_APPROVAL" if execution_plan.approval_required else "READY"
        item = Orchestration(id=oid, request=req.request, application=req.application, environment=req.environment, status=status, plan=execution_plan)
        store.save(item)
        return item
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/orchestrations/{oid}")
def get(oid: str):
    item = store.get(oid)
    if not item:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return item

@app.post("/orchestrations/{oid}/approve")
def approve(oid: str):
    item = store.get(oid)
    if not item:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    if item.status != "AWAITING_APPROVAL":
        raise HTTPException(status_code=409, detail=f"Cannot approve orchestration in state {item.status}")
    item.status = "READY"
    store.save(item)
    return item

@app.post("/orchestrations/{oid}/execute")
def execute(oid: str):
    item = store.get(oid)
    if not item:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    if item.status != "READY":
        raise HTTPException(status_code=409, detail=f"Cannot execute orchestration in state {item.status}")
    client = GitHubClient()
    item.status = "RUNNING"
    store.save(item)
    try:
        for step in item.plan.steps:
            wf = get_workflow(step.workflow)
            repository = wf["repository"]
            if repository == "OWNER/REPO":
                repository = f"{client.default_owner}/{client.default_repo}"
            result = client.dispatch(repository, wf["workflow"], step.inputs)
            result["step"] = step.step
            result["capability"] = step.workflow
            item.runs.append(result)
            item.current_step = step.step
            store.save(item)
        item.status = "DISPATCHED"
        store.save(item)
        return item
    except Exception as exc:
        item.status = "FAILED_TO_DISPATCH"
        item.error = str(exc)
        store.save(item)
        raise HTTPException(status_code=502, detail=str(exc))
