import re
from .models import ExecutionPlan, PlanRequest, PlanStep
from .policy import approval_required, validate_plan

UPGRADE_RE = re.compile(r"upgrade|rhel\s*9|migration|reprovision", re.I)

def build_plan(req: PlanRequest) -> ExecutionPlan:
    text = req.request
    steps = []
    if UPGRADE_RE.search(text):
        names = ["terraform_plan", "backup_server", "provision_server", "configure_tomcat", "validate_application"]
        reasons = [
            "Validate infrastructure changes before mutation",
            "Create a recovery point before upgrade/reprovision",
            "Provision the target server state",
            "Apply application server configuration",
            "Verify application health before declaring success",
        ]
    else:
        names = ["terraform_plan"]
        reasons = ["Validate the requested infrastructure change"]
    for i, (name, reason) in enumerate(zip(names, reasons), 1):
        inputs = {"application": req.application, "environment": req.environment}
        if name in {"configure_tomcat", "validate_application"}:
            inputs = {"instance_id": "${provision_server.instance_id}"}
        steps.append(PlanStep(step=i, workflow=name, reason=reason, inputs=inputs, risk="registered"))
    plan = ExecutionPlan(request=text, application=req.application, environment=req.environment, steps=steps, approval_required=False)
    raw = plan.model_dump()
    raw["branch"] = "main"
    validate_plan(raw)
    plan.approval_required = approval_required(raw)
    return plan
