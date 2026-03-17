# ag-z

Agent-Z/
├── apprunner.yaml              ← app runner build & run
├── README.md                   ← what this is
├── backend/
│   ├── app.py                  ← the entire agent (425 lines)
│   └── requirements.txt        ← python dependencies (7 lines)






version: 1.0
runtime: python311
build:
  commands:
    build:
      - pip install -r backend/requirements.txt
run:
  command: gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --chdir backend app:app
  network:
    port: 8080
    env: PORT
  env:
    - name: PORT
      value: "8080"
```

Commit.

**File 3 — type `backend/requirements.txt` in the filename box (the slash creates the folder), paste:**
```
flask==3.1.0
python-dotenv==1.1.0
boto3==1.36.0
requests==2.32.3
langgraph==0.2.60
langchain-core==0.3.28
gunicorn==23.0.0
```

Commit.

**File 4 — type `backend/app.py` in the filename box, paste the entire contents from the app.py I gave you earlier** (the 425-line Agent-Z file — download it from the files I shared above, open it, copy all, paste).

Commit.

Your repo now has 5 files in 2 folders. Done.

---

## STEP 1: Create GitHub OAuth App (5 min)

1. Go to `https://github.com`
2. Click your **profile picture** (top-right) > **Settings**
3. Scroll left sidebar all the way down > click **"Developer settings"**
4. Left sidebar > click **"OAuth Apps"**
5. Click green button **"New OAuth App"**
6. Fill in:
```
Application name:            Agent-Z
Homepage URL:                http://localhost:8080
Application description:     (leave empty)
Authorization callback URL:  http://localhost:8080/callback
```

7. Click **"Register application"**
8. You see **Client ID** near the top — copy it
9. Open Notepad. Paste it:
```
GITHUB_CLIENT_ID=Ov23lixxxxxxxxxx
```

10. Click **"Generate a new client secret"**
11. A long string appears — **copy it RIGHT NOW** (only visible once)
12. Paste in notepad:
```
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Keep notepad open.

---

## STEP 2: Enable Bedrock Model Access (2 min)

1. Go to `https://console.aws.amazon.com`
2. Top-right corner — click the region name > select **"US East (Ohio) us-east-2"**
3. Search bar at top > type `Bedrock` > click **"Amazon Bedrock"**
4. Left sidebar > find **"Model access"** > click it
5. Click **"Modify model access"** (or "Manage model access")
6. Find **"Anthropic"** > expand it
7. Check the box next to **"Claude 3.5 Sonnet v2"** (or whatever Claude is available)
8. Click **"Next"** or **"Save changes"**
9. Wait until status says **"Access granted"**

---

## STEP 3: Create AgentCore Identity (5 min)

1. You should still be in Bedrock console. If not: search `Bedrock`
2. Left sidebar > look for **"AgentCore"** > expand it
3. Click **"OAuth Clients"** (or "Identities" — whatever you see)
4. Click **"Create"**
5. Fill in:
```
Name:    agent-z-github
```

6. Provider: **"Custom provider"** (or pick GitHub from "Included provider" if it's there)
7. Configuration type: **"Manual config"**
8. Fill in:
```
Client ID:                (paste GITHUB_CLIENT_ID from your notepad)
Client secret:            (paste GITHUB_CLIENT_SECRET from your notepad)
Issuer:                   https://github.com
Authorization endpoint:   https://github.com/login/oauth/authorize
Token endpoint:           https://github.com/login/oauth/access_token
```

9. If you see "Response types" > click "Add response type" > type `code`
10. Click **"Create"**
11. You'll see an **ARN** on the page. Copy it. Paste in notepad:
```
GITHUB_AGENT_IDENTITY_ARN=arn:aws:bedrock:us-east-2:xxxxxxxxx:identity/agent-z-github-xxxxx



















Endpoints:
  GET  /authorize?session_id=xxx  → starts GitHub OAuth
  POST /run                       → runs the agent
  GET  /health                    → health check
