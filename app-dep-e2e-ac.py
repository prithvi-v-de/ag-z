"""
AgentCore Runtime / Identity / Gateway...
"""

import os, json, logging, time
import boto3, requests
from typing import TypedDict, Annotated, Literal
from operator import add
from bedrock_agentcore import BedrockAgentCoreApp
from langgraph.graph import StateGraph, END

# ============================================================
#  LOGGING & CONFIG
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
log = logging.getLogger("agent-z")

REGION = os.getenv("AWS_REGION", "us-east-2")
# Still using your whitelisted Opus 4.5 model!
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-5-20251101-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# 1. Initialize the AgentCore App (Goodbye Flask!)
app = BedrockAgentCoreApp()

# ============================================================
#  LANGGRAPH AGENT STATE & NODES
# ============================================================
# Notice we removed session_id. AgentCore Memory handles sessions automatically!
class AgentState(TypedDict):
    action: str
    target: str
    status: str
    github_data: dict
    bedrock_analysis: str
    error: str
    messages: Annotated[list, add]

def node_scope_check(state: AgentState) -> dict:
    log.info(f"NODE: scope_check for {state['action']}/{state['target']}")
    github_keywords = ["github", "repo", "org", "user", "pr"]
    if any(k in f"{state['action']} {state['target']}".lower() for k in github_keywords):
        return {"status": "scope_passed", "messages": ["✅ Scope check passed"]}
    return {"status": "rejected", "error": "Not a GitHub resource", "messages": ["🚫 Scope check REJECTED"]}

def node_fetch_github(state: AgentState) -> dict:
    log.info("NODE: fetch_github")
    
    # 🌟 THE MAGIC: AgentCore Identity & Gateway handle the OAuth token.
    # Instead of hitting api.github.com directly with a manual token, 
    # we just hit our secure AgentCore Gateway URL, which injects the token for us.
    GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_URL") 
    
    resp = requests.get(
        f"{GATEWAY_URL}/{state['action']}?target={state['target']}", 
        headers={"Accept": "application/json"}
    )
    
    data = resp.json() if resp.status_code == 200 else {"error": "Failed to fetch from Gateway"}
    return {"github_data": data, "status": "data_fetched", "messages": [f"📦 GitHub data fetched natively!"]}

def node_call_bedrock(state: AgentState) -> dict:
    log.info("NODE: call_bedrock")
    prompt = f"Analyze this GitHub data:\n{json.dumps(state['github_data'])[:3000]}\nGive a brief summary."
    
    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }),
        guardrailIdentifier="dnnsxv3hu09f",  # Your mandatory corporate guardrail
        guardrailVersion="1"
    )
    text = json.loads(resp["body"].read())["content"][0]["text"]
    return {"bedrock_analysis": text, "status": "complete", "messages": ["🤖 Bedrock analysis complete"]}

def node_format_error(state: AgentState) -> dict:
    return {"messages": [f"❌ Error: {state.get('error')}"]}

# Routing
def route_after_scope(state: AgentState) -> Literal["fetch_github", "format_error"]:
    return "fetch_github" if state["status"] == "scope_passed" else "format_error"

# Build Graph (Notice we removed the manual check_token node!)
g = StateGraph(AgentState)
g.add_node("scope_check", node_scope_check)
g.add_node("fetch_github", node_fetch_github)
g.add_node("call_bedrock", node_call_bedrock)
g.add_node("format_error", node_format_error)

g.set_entry_point("scope_check")
g.add_conditional_edges("scope_check", route_after_scope)
g.add_edge("fetch_github", "call_bedrock")
g.add_edge("call_bedrock", END)
g.add_edge("format_error", END)

agent = g.compile()

# ============================================================
#  AGENTCORE ENTRYPOINT
# ============================================================
# 3. This replaces your Flask /run route and the AWS Lambda handler!
@app.entrypoint
def invoke(payload):
    log.info("🚀 AgentCore Invoked!")
    
    # Extract data sent from SharePoint via AgentCore Gateway
    action = payload.get("action", "org_info")
    target = payload.get("target", "aws")
    
    # Run the LangGraph agent
    result = agent.invoke({
        "action": action, 
        "target": target,
        "status": "", "github_data": {}, "bedrock_analysis": "", "error": "", "messages": []
    })
    
    # Return the clean result back through the AgentCore Gateway to SharePoint
    return {
        "status": result.get("status"),
        "bedrock_analysis": result.get("bedrock_analysis"),
        "trace": result.get("messages")
    }
