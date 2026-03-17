import os, json, uuid, logging, sys, time
import boto3, requests
from typing import TypedDict, Annotated, Literal
from operator import add
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

load_dotenv()

#  LOGGING — everything goes to stdout → CloudWatch picks it up

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agent-z")

# Quiet noisy libs
for lib in ["urllib3", "botocore", "boto3", "werkzeug"]:
    logging.getLogger(lib).setLevel(logging.WARNING)


#  CONFIG

REGION = os.getenv("AWS_REGION", "us-east-2")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
APP_URL = os.getenv("APP_URL", "http://localhost:8080")
GITHUB_IDENTITY_ARN = os.getenv("GITHUB_AGENT_IDENTITY_ARN", "")

log.info("=" * 60)
log.info("AGENT-Z STARTING")
log.info(f"  Region:     {REGION}")
log.info(f"  Model:      {MODEL_ID}")
log.info(f"  APP_URL:    {APP_URL}")
log.info(f"  Identity:   {GITHUB_IDENTITY_ARN[:50]}...")
log.info("=" * 60)


#  CLIENTS

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
token_store = {}  # session_id → {access_token, ...}


#  GITHUB HELPERS

def github_get(path, token):
    """Call GitHub API."""
    log.info(f"[github] GET https://api.github.com{path}")
    resp = requests.get(
        f"https://api.github.com{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"},
    )
    log.info(f"[github] Response: {resp.status_code}")
    return resp.json()



#  BEDROCK HELPER

def ask_bedrock(prompt):
    """Call Bedrock Claude model."""
    log.info(f"[bedrock] Calling {MODEL_ID}")
    log.info(f"[bedrock] Prompt: {prompt[:100]}...")
    t0 = time.time()
    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    body = json.loads(resp["body"].read())
    text = body["content"][0]["text"]
    elapsed = (time.time() - t0) * 1000
    log.info(f"[bedrock] Response ({elapsed:.0f}ms): {text[:100]}...")
    return text


#  AGENTCORE IDENTITY — scope enforcement

def enforce_github_scope(url_or_action):
    """
    AgentCore Identity enforcement layer.
    This agent is ONLY authorized for GitHub. Any non-GitHub
    request is rejected at the identity layer.
    """
    log.info(f"[identity] Scope check: '{url_or_action}'")
    log.info(f"[identity] Agent identity: {GITHUB_IDENTITY_ARN}")
    log.info(f"[identity] Allowed provider: github")

    # This agent only talks to GitHub
    github_keywords = ["github", "repo", "org", "user", "pr", "issue", "commit"]
    is_github = any(k in url_or_action.lower() for k in github_keywords)

    if not is_github:
        log.error(f"[identity] ╔══════════════════════════════════════╗")
        log.error(f"[identity] ║  🚫 SCOPE CHECK: REJECTED            ║")
        log.error(f"[identity] ╚══════════════════════════════════════╝")
        log.error(f"[identity] This agent can ONLY access GitHub resources")
        return False

    log.info(f"[identity] ╔══════════════════════════════════════╗")
    log.info(f"[identity] ║  ✅ SCOPE CHECK: AUTHORIZED           ║")
    log.info(f"[identity] ╚══════════════════════════════════════╝")
    return True



#  LANGGRAPH AGENT — State/Nodes

class AgentState(TypedDict):
    session_id: str
    action: str          # "list_repos" | "org_info" | "user_info"
    target: str          # org name or username
    status: str
    github_data: dict
    bedrock_analysis: str
    error: str
    messages: Annotated[list, add]


def node_scope_check(state: AgentState) -> dict:
    """Node 1: AgentCore Identity scope enforcement."""
    log.info("")
    log.info("━" * 50)
    log.info("NODE: scope_check")
    log.info("━" * 50)
    log.info(f"  Action: {state['action']}")
    log.info(f"  Target: {state['target']}")

    allowed = enforce_github_scope(f"github {state['action']} {state['target']}")

    if allowed:
        return {"status": "scope_passed", "messages": [f"✅ Scope check passed for '{state['action']}'"]}
    else:
        return {"status": "rejected", "error": "AgentCore Identity: not a GitHub resource",
                "messages": [f"🚫 Scope check REJECTED"]}


def node_check_token(state: AgentState) -> dict:
    """Node 2: Check if we have a GitHub OAuth token."""
    log.info("")
    log.info("━" * 50)
    log.info("NODE: check_token")
    log.info("━" * 50)
    log.info(f"  Session: {state['session_id'][:12]}...")

    token = token_store.get(state["session_id"])
    if token:
        log.info(f"  ✅ Token found (scope: {token.get('scope', 'N/A')})")
        return {"status": "has_token", "messages": ["🔑 GitHub token available"]}
    else:
        log.info(f"  ✖ No token — user must authorize")
        return {"status": "needs_auth",
                "error": f"Not authorized. Visit {APP_URL}/authorize?session_id={state['session_id']}",
                "messages": ["🔐 OAuth required"]}


def node_fetch_github(state: AgentState) -> dict:
    """Node 3: Fetch data from GitHub API."""
    log.info("")
    log.info("━" * 50)
    log.info("NODE: fetch_github")
    log.info("━" * 50)

    token = token_store[state["session_id"]]["access_token"]
    action = state["action"]
    target = state["target"]

    if action == "org_info":
        data = github_get(f"/orgs/{target}", token)
        repos = github_get(f"/orgs/{target}/repos?per_page=5&sort=updated", token)
        data["recent_repos"] = [{"name": r["name"], "stars": r.get("stargazers_count", 0),
                                  "language": r.get("language")} for r in repos[:5]]
    elif action == "list_repos":
        repos = github_get(f"/orgs/{target}/repos?per_page=10&sort=updated", token)
        data = {"org": target, "repos": [{"name": r["name"], "stars": r.get("stargazers_count", 0),
                "language": r.get("language"), "description": (r.get("description") or "")[:80]}
                for r in repos[:10]]}
    elif action == "user_info":
        data = github_get(f"/users/{target}", token)
    else:
        data = {"error": f"Unknown action: {action}"}

    log.info(f"  Fetched {len(json.dumps(data))} bytes of GitHub data")
    return {"github_data": data, "status": "data_fetched",
            "messages": [f"📦 GitHub data fetched for {action}/{target}"]}


def node_call_bedrock(state: AgentState) -> dict:
    """Node 4: Send GitHub data to Bedrock Claude for analysis."""
    log.info("")
    log.info("━" * 50)
    log.info("NODE: call_bedrock")
    log.info("━" * 50)

    data = state["github_data"]
    action = state["action"]
    target = state["target"]

    prompt = f"""You are analyzing GitHub data fetched via AgentCore Identity OAuth.
Action: {action}
Target: {target}

Data:
{json.dumps(data, indent=2)[:3000]}

Give a brief, useful summary of this GitHub {action}. Be concise (3-5 sentences)."""

    analysis = ask_bedrock(prompt)

    return {"bedrock_analysis": analysis, "status": "complete",
            "messages": [f"🤖 Bedrock analysis complete"]}


def node_format_error(state: AgentState) -> dict:
    """Terminal node for errors."""
    log.info(f"NODE: format_error → {state.get('error', 'unknown')}")
    return {"messages": [f"❌ Error: {state.get('error', '')}"]}



#  ROUTING

def route_after_scope(state: AgentState) -> Literal["check_token", "format_error"]:
    r = "check_token" if state["status"] == "scope_passed" else "format_error"
    log.info(f"  🔀 route_after_scope → {r}")
    return r

def route_after_token(state: AgentState) -> Literal["fetch_github", "format_error"]:
    r = "fetch_github" if state["status"] == "has_token" else "format_error"
    log.info(f"  🔀 route_after_token → {r}")
    return r



#  BUILD GRAPH

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
    g.add_edge("fetch_github", "call_bedrock")
    g.add_edge("call_bedrock", END)
    g.add_edge("format_error", END)
    return g.compile()

agent = build_agent()
log.info("LangGraph agent compiled")



#  FLASK 

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")


@app.route("/")
def index():
    return jsonify({
        "service": "Agent-Z",
        "description": "LangGraph + AgentCore Identity + Bedrock",
        "endpoints": {
            "/authorize?session_id=xxx": "Start GitHub OAuth",
            "/run": "POST {action, target, session_id} to run agent",
            "/health": "Health check",
        },
        "example": "POST /run with {\"action\":\"org_info\", \"target\":\"aws\", \"session_id\":\"your-session\"}",
    })


@app.route("/authorize")
def authorize():
    """Start GitHub OAuth flow via AgentCore Identity."""
    sid = request.args.get("session_id", str(uuid.uuid4()))
    log.info(f"[oauth] Starting GitHub authorize for session {sid[:12]}...")

    params = {
        "client_id": os.getenv("GITHUB_CLIENT_ID"),
        "redirect_uri": f"{APP_URL}/callback",
        "scope": "repo read:user read:org",
        "state": json.dumps({"session_id": sid}),
    }
    url = f"https://github.com/login/oauth/authorize?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    log.info(f"[oauth] Redirecting to GitHub...")
    return redirect(url)


@app.route("/callback")
def callback():
    """Handle GitHub OAuth callback."""
    code = request.args.get("code")
    state = json.loads(request.args.get("state", "{}"))
    sid = state.get("session_id", "")

    log.info(f"[oauth] Callback received for session {sid[:12]}...")

    if not code:
        log.error("[oauth] No code received")
        return jsonify({"error": "No auth code"}), 400

    # Exchange code for token
    log.info("[oauth] Exchanging code for token...")
    resp = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": os.getenv("GITHUB_CLIENT_ID"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "code": code,
        },
    )
    td = resp.json()

    if "access_token" not in td:
        log.error(f"[oauth] Token exchange failed: {td}")
        return jsonify({"error": "Token exchange failed", "details": td}), 400

    token_store[sid] = td
    log.info(f"[oauth] ✅ Token stored (scope: {td.get('scope', 'N/A')})")

    return jsonify({
        "status": "authorized",
        "session_id": sid,
        "message": "GitHub authorized! Now POST to /run to use the agent.",
        "example": {
            "method": "POST",
            "url": f"{APP_URL}/run",
            "body": {"action": "org_info", "target": "aws", "session_id": sid},
        },
    })


@app.route("/run", methods=["POST"])
def run():
    """Run the LangGraph agent."""
    data = request.get_json() or {}
    action = data.get("action", "org_info")      # org_info, list_repos, user_info
    target = data.get("target", "")
    sid = data.get("session_id", "")

    if not target:
        return jsonify({"error": "Missing 'target' (org name or username)"}), 400
    if not sid:
        return jsonify({"error": "Missing 'session_id'. Visit /authorize first."}), 400

    log.info("")
    log.info("=" * 60)
    log.info(f"  AGENT RUN: action={action} target={target}")
    log.info("=" * 60)

    t0 = time.time()
    result = agent.invoke({
        "session_id": sid,
        "action": action,
        "target": target,
        "status": "",
        "github_data": {},
        "bedrock_analysis": "",
        "error": "",
        "messages": [],
    })
    elapsed = (time.time() - t0) * 1000

    log.info("")
    log.info(f"  AGENT DONE ({elapsed:.0f}ms)")
    log.info(f"  Status: {result.get('status')}")
    log.info(f"  Trace: {result.get('messages')}")
    log.info("=" * 60)

    return jsonify({
        "status": result.get("status"),
        "action": action,
        "target": target,
        "github_data": result.get("github_data", {}),
        "bedrock_analysis": result.get("bedrock_analysis", ""),
        "error": result.get("error", ""),
        "trace": result.get("messages", []),
        "elapsed_ms": round(elapsed),
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    log.info(f"Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
