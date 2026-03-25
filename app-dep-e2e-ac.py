import os, json, requests, boto3
from bedrock_agentcore import BedrockAgentCoreApp

REGION = os.getenv("AWS_REGION", "us-west-2")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-5-20251101-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_URL")
    
    # 1. Fetch from Gateway (We will hardcode 'aws' for this quick test)
    resp = requests.get(f"{GATEWAY_URL}/orgs/aws", headers={"Accept": "application/json"})
    
    if resp.status_code != 200:
        return {"error": f"Gateway failed with status {resp.status_code}"}
        
    github_data = resp.json()
    
    # 2. Call Bedrock
    prompt = f"Analyze this GitHub data:\n{json.dumps(github_data)[:3000]}\nGive a brief summary."
    
    bedrock_resp = bedrock.invoke_model(
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
    
    text = json.loads(bedrock_resp["body"].read())["content"][0]["text"]
    
    return {"result": text}
