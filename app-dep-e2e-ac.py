import os, json, logging
import boto3, requests
from typing import TypedDict, Annotated, Literal
from operator import add
from bedrock_agentcore import BedrockAgentCoreApp
from langgraph.graph import StateGraph, END

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent-z")

REGION = os.getenv("AWS_REGION", "us-west-2")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-5-20251101-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
app = BedrockAgentCoreApp()

class AgentState(TypedDict):
    action: str
    target: str
    status: str
    github_data: dict
    bedrock_analysis: str
    error: str

def node_scope_check(state: AgentState):
    log.info("NODE: scope_check")
    return {"status": "scope_passed"} if "aws" in state['target'].lower() else {"status": "rejected", "error": "Out of scope"}

def node_fetch_github(state: AgentState):
    log.info("NODE: fetch_github")
    GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_URL") 
    
    # Fetch natively through your new AgentCore Gateway
    resp = requests.get(f"{GATEWAY_URL}/orgs/{state['target']}", headers={"Accept": "application/json"})
    data = resp.json() if resp.status_code == 200 else {"error": f"Gateway fetch failed: {resp.status_code}"}
    return {"github_data": data, "status": "data_fetched"}

def node_call_bedrock(state: AgentState):
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
        guardrailIdentifier="dnnsxv3hu09f",
        guardrailVersion="1"
    )
    text = json.loads(resp["body"].read())["content"][0]["text"]
    return {"bedrock_analysis": text, "status": "complete"}

def route_after_scope(state: AgentState) -> Literal["fetch_github", "format_error"]:
    return "fetch_github" if state["status"] == "scope_passed" else "format_error"

def node_format_error(state: AgentState):
    return {"status": "error"}

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

@app.entrypoint
def invoke(payload):
    log.info("🚀 AgentCore Invoked LangGraph!")
    action = payload.get("action", "org_info")
    target = payload.get("target", "aws")
    
    result = agent.invoke({"action": action, "target": target, "status": "", "github_data": {}, "bedrock_analysis": "", "error": ""})
    return {"result": result.get("bedrock_analysis") or result.get("error")}
