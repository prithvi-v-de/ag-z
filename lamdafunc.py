import os, json, uuid, logging, sys, time
import boto3, requests
from typing import TypedDict, Annotated, Literal
from operator import add
from urllib.parse import parse_qs
from langgraph.graph import StateGraph, END

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("agent-z")
for lib in ["urllib3", "botocore", "boto3"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-5-20251101-v1:0")
APP_URL = os.getenv("APP_URL", "http://localhost:8080")
GITHUB_IDENTITY_ARN = os.getenv("GITHUB_AGENT_IDENTITY_ARN", "")
GH_BASE = "https://gitprod.statestr.com"
GH_API = "https://gitprod.statestr.com/api/v3"
bedrock = boto3.client("bedrock-runtime", region_name=REGION)
token_store = {}

def github_get(path, token):
    url = f"{GH_API}{path}"
    log.info(f"[github] GET {url}")
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"})
    log.info(f"[github] {r.status_code}")
    return r.json()

def ask_bedrock(prompt):
    log.info(f"[bedrock] Calling {MODEL_ID}")
    t0 = time.time()
    r = bedrock.invoke_model(modelId=MODEL_ID, contentType="application/json", accept="application/json", body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}))
    text = json.loads(r["body"].read())["content"][0]["text"]
    log.info(f"[bedrock] Done ({(time.time()-t0)*1000:.0f}ms)")
    return text

def enforce_github_scope(action_text):
    keywords = ["github", "repo", "org", "user", "pr", "issue", "commit"]
    allowed = any(k in action_text.lower() for k in keywords)
    log.info(f"[identity] Scope '{action_text}' -> {'ALLOWED' if allowed else 'REJECTED'}")
    return allowed

class AgentState(TypedDict):
    session_id: str
    action: str
    target: str
    status: str
    github_data: dict
    bedrock_analysis: str
    error: str
    messages: Annotated[list, add]

def node_scope_check(state):
    log.info("NODE: scope_check")
    if enforce_github_scope(f"github {state['action']} {state['target']}"):
        return {"status": "scope_passed", "messages": ["scope passed"]}
    return {"status": "rejected", "error": "Not a GitHub resource", "messages": ["scope rejected"]}

def node_check_token(state):
    log.info("NODE: check_token")
    token = token_store.get(state["session_id"])
    if token:
        log.info("Token found")
        return {"status": "has_token", "messages": ["token ok"]}
    log.info("No token")
    return {"status": "needs_auth", "error": f"Not authorized. Visit {APP_URL}/authorize?session_id={state['session_id']}", "messages": ["needs auth"]}

def node_fetch_github(state):
    log.info("NODE: fetch_github")
    token = token_store[state["session_id"]]["access_token"]
    action = state["action"]
    target = state["target"]
    if action == "org_info":
        data = github_get(f"/orgs/{target}", token)
        repos = github_get(f"/orgs/{target}/repos?per_page=5&sort=updated", token)
        data["recent_repos"] = [{"name": r["name"], "stars": r.get("stargazers_count", 0), "language": r.get("language")} for r in repos[:5]]
    elif action == "list_repos":
        repos = github_get(f"/orgs/{target}/repos?per_page=10&sort=updated", token)
        data = {"org": target, "repos": [{"name": r["name"], "stars": r.get("stargazers_count", 0), "language": r.get("language"), "description": (r.get("description") or "")[:80]} for r in repos[:10]]}
    elif action == "user_info":
        data = github_get(f"/users/{target}", token)
    else:
        data = {"error": f"Unknown action: {action}"}
    log.info(f"Fetched {len(json.dumps(data))} bytes")
    return {"github_data": data, "status": "data_fetched", "messages": [f"fetched {action}/{target}"]}

def node_call_bedrock(state):
    log.info("NODE: call_bedrock")
    prompt = f"""Analyze this GitHub data. Action: {state['action']}, Target: {state['target']}
Data: {json.dumps(state['github_data'], indent=2)[:3000]}
Give a brief 3-5 sentence summary."""
    analysis = ask_bedrock(prompt)
    return {"bedrock_analysis": analysis, "status": "complete", "messages": ["bedrock done"]}

def node_format_error(state):
    log.info(f"NODE: error -> {state.get('error')}")
    return {"messages": [f"error: {state.get('error', '')}"]}

def route_after_scope(state):
    return "check_token" if state["status"] == "scope_passed" else "format_error"

def route_after_token(state):
    return "fetch_github" if state["status"] == "has_token" else "format_error"

def build_agent():
    g = StateGraph(AgentState)
    g.add_node("scope_check", node_scope_check)
    g.add_node("check_token", node_check_token)
    g.add_node("fetch_github", node_fetch_github)
    g.add_node("call_bedrock", node_call_bedrock)
    g.add_node("format_error", node_format_error)
    g.set_entry_point("scope_check")
    g.add_conditional_edges("scope_check", route_after_scope)
    g.add_conditional_edges("check_token", route_after_token)
    g.add_edge("fetch_github", END)
    g.add_edge("call_bedrock", END)
    g.add_edge("format_error", END)
    return g.compile()

agent = build_agent()
log.info("LangGraph agent compiled")

def ok(body):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def err(code, msg):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": msg})}

def lambda_handler(event, context):
    try:
        rc = event.get("requestContext", {}).get("http", {})
        method = rc.get("method", "GET")
        path = event.get("rawPath", "/")
        qs = event.get("rawQueryString", "")
        body = event.get("body") or ""
        if event.get("isBase64Encoded") and body:
            import base64
            body = base64.b64decode(body).decode("utf-8")

        if path == "/health":
            return ok({"status": "healthy"})

        if path == "/":
            return ok({"service": "Agent-Z", "description": "LangGraph + AgentCore Identity + Bedrock"})

        if path == "/authorize":
            params = parse_qs(qs)
            sid = params.get("session_id", [str(uuid.uuid4())])[0]
            p = {"client_id": os.getenv("GITHUB_CLIENT_ID"), "redirect_uri": f"{APP_URL}/callback", "scope": "repo read:user read:org", "state": json.dumps({"session_id": sid})}
            url = f"{GH_BASE}/login/oauth/authorize?" + "&".join(f"{k}={v}" for k, v in p.items())
            return {"statusCode": 302, "headers": {"Location": url}, "body": ""}

        if path == "/callback":
            params = parse_qs(qs)
            code = params.get("code", [""])[0]
            raw_state = params.get("state", ["{}"])[0]
            state = json.loads(raw_state)
            sid = state.get("session_id", "")
            if not code:
                return err(400, "No auth code")
            resp = requests.post(f"{GH_BASE}/login/oauth/access_token", headers={"Accept": "application/json"}, data={"client_id": os.getenv("GITHUB_CLIENT_ID"), "client_secret": os.getenv("GITHUB_CLIENT_SECRET"), "code": code})
            td = resp.json()
            if "access_token" not in td:
                return err(400, f"Token exchange failed: {td}")
            token_store[sid] = td
            log.info(f"Token stored for session {sid}")
            return ok({"status": "authorized", "session_id": sid, "message": "GitHub authorized! POST to /run to use the agent."})

        if path == "/run" and method == "POST":
            data = json.loads(body) if body else {}
            action = data.get("action", "org_info")
            target = data.get("target", "")
            sid = data.get("session_id", "")
            if not target:
                return err(400, "Missing target")
            if not sid:
                return err(400, "Missing session_id")
            log.info(f"AGENT RUN: {action} / {target}")
            t0 = time.time()
            result = agent.invoke({"session_id": sid, "action": action, "target": target, "status": "", "github_data": {}, "bedrock_analysis": "", "error": "", "messages": []})
            elapsed = (time.time() - t0) * 1000
            log.info(f"AGENT DONE ({elapsed:.0f}ms) status={result.get('status')}")
            return ok({"status": result.get("status"), "action": action, "target": target, "github_data": result.get("github_data", {}), "bedrock_analysis": result.get("bedrock_analysis", ""), "error": result.get("error", ""), "trace": result.get("messages", []), "elapsed_ms": round(elapsed)})

        return err(404, "Not found")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e), "type": type(e).__name__})}
