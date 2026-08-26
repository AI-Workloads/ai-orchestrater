from .registry import get_workflow, policies

class PolicyError(Exception):
    pass

def validate_plan(plan: dict) -> bool:
    cfg = policies()
    env = plan["environment"]
    section = cfg["production"] if env == "prod" else cfg["non_production"]
    if plan.get("branch", "main") != section["allowed_branch"]:
        raise PolicyError("Execution branch is not permitted")
    for step in plan["steps"]:
        wf = get_workflow(step["workflow"])
        if env not in wf.get("environments", []):
            raise PolicyError(f"{step['workflow']} is not allowed in {env}")
        if step["workflow"] in section.get("prohibited_workflows", []):
            raise PolicyError(f"{step['workflow']} is prohibited")
    return True

def approval_required(plan: dict) -> bool:
    cfg = policies()
    risks = cfg["production"]["require_approval_risk"] if plan["environment"] == "prod" else cfg["non_production"]["require_approval_risk"]
    return any(get_workflow(s["workflow"])["risk"] in risks for s in plan["steps"])
