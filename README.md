```

cd /d C:\afp-py-test-br
rmdir /s /q package
mkdir package
pip install --target .\package --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: flask requests langgraph langchain-core


copy app.py .\package\app.py
cd package
del C:\afp-py-test-br\agent-z.zip
tar -a -cf C:\afp-py-test-br\agent-z.zip *
cd C:\afp-py-test-br

```

---

## STEP 1: Create IAM Role for Lambda

1. AWS Console > make sure **Ohio (us-east-2)**
2. Search **"IAM"** > click it
3. Left sidebar > **"Roles"** > **"Create role"**
4. Trusted entity: **AWS service**
5. Use case: find **Lambda** in the dropdown > select it
6. Click **"Next"**
7. Search and check these 2 policies (search one at a time):
   - `AWSLambdaBasicExecutionRole`
   - `AmazonBedrockFullAccess`
8. Click **"Next"**
9. Role name: `AgentZLambdaRole`
10. Click **"Create role"**

---

## STEP 2: Create Lambda Function

1. AWS Console > search **"Lambda"** > click it
2. Make sure **Ohio (us-east-2)**
3. Click **"Create function"**
4. Select **"Author from scratch"**
5. Function name: `agent-z`
6. Runtime: **Python 3.12**
7. Architecture: **x86_64**
8. Click **"Change default execution role"** to expand it
9. Select **"Use an existing role"**
10. In the dropdown, select **AgentZLambdaRole**
11. Click **"Create function"**

---

## STEP 3: Upload Your Zip

1. You're on the function page, on the **"Code"** tab
2. Click the **"Upload from"** dropdown
3. Click **".zip file"**
4. Click **"Upload"**
5. Navigate to `C:\afp-py-test-br\agent-z.zip` > select it
6. Click **"Save"**
7. Wait a few seconds for upload to finish

---

## STEP 4: Fix the Handler

1. Still on the Code tab, scroll down to **"Runtime settings"**
2. Click **"Edit"**
3. Change Handler from `lambda_function.lambda_handler` to:
```
app.lambda_handler
```

4. Click **"Save"**

---

## STEP 5: Set Timeout and Memory

1. Click **"Configuration"** tab (next to Code at the top)
2. Click **"General configuration"** on the left side
3. Click **"Edit"**
4. Memory: `512`
5. Timeout: change to `2` min `0` sec
6. Click **"Save"**

---

## STEP 6: Add Environment Variables

1. Still on Configuration tab
2. Left side > click **"Environment variables"**
3. Click **"Edit"**
4. Click **"Add environment variable"** for each of these 7:
```
Key:    AWS_REGION
Value:  us-east-2
```
```
Key:    GITHUB_AGENT_IDENTITY_ARN
Value:  (paste your ARN from notepad)
```
```
Key:    GITHUB_CLIENT_ID
Value:  (paste from notepad)
```
```
Key:    GITHUB_CLIENT_SECRET
Value:  (paste from notepad)
```
```
Key:    APP_URL
Value:  https://placeholder
```
```
Key:    FLASK_SECRET_KEY
Value:  anyrandomtext123
```
```
Key:    BEDROCK_MODEL_ID
Value:  anthropic.claude-haiku-4-5-20251001-v1:0
```

5. Click **"Save"**

---

## STEP 7: Create API/GWAY


- AWS Console > search "API Gateway" > click it
- Find "HTTP API" > click "Build"
- Click "Add integration"
- Integration type: Lambda
- Lambda function: select afp-py-test-lambdafunc (your function)
- API name: xyz-api
- Click "Next"

Configure routes:

```
In the left sidebar, click "Routes" (under Develop)
Click "Create"
Method: ANY
Path: /{proxy+}
Click "Create"
Now you'll see the route listed. Click on ANY /{proxy+}
Click "Attach integration"
Select your Lambda function afp-py-test-lambdafunc
Click "Attach integration"

Now create one more route for the root path:

Click "Routes" again in the left sidebar
Click "Create"
Method: ANY
Path: /
Click "Create"
Click on ANY /
Click "Attach integration"
Select afp-py-test-lambdafunc
Click "Attach integration"

Now deploy:

Left sidebar > click "Stages" (under Deploy)
Click the "Deploy" button (top right)
```
Stages:
```
Stage name: leave as $default
Auto-deploy: ON
Click "Next"
```
Review:
```
Click "Create"

You'll see an "Invoke URL" — looks like:
https://abc123xyz.execute-api.us-east-1.amazonaws.com
Copy that URL. That's your endpoint — works exactly like the Function URL would have.
```
Now continue with the same steps:
Update APP_URL in Lambda:
```
Lambda > Configuration > Environment variables > Edit
Change APP_URL to your API Gateway URL
Save
```
Update GitHub OAuth callback:
```
github.com > Developer settings > your app
Change callback to: https://abc123xyz.execute-api.us-east-1.amazonaws.com/callback
Change homepage too
Update application
```

---

## STEP 8: Update APP_URL

1. Configuration > left side > **"Environment variables"** > **"Edit"**
2. Find `APP_URL`
3. Change `https://placeholder` to your Function URL (the one you just copied)
4. **NO trailing space**
5. Click **"Save"**

---

## STEP 9: Update GitHub OAuth Callback

1. Go to your GitHub > Developer settings > OAuth Apps > click your app
2. Change **"Authorization callback URL"** to:
```
https://abc123xyz.lambda-url.us-east-2.on.aws/callback
```

3. Change **"Homepage URL"** to:
```
https://abc123xyz.lambda-url.us-east-2.on.aws
```

4. Click **"Update application"**

---

## STEP 10: Test

**Health check** — open browser:
```
https://abc123xyz.lambda-url.us-east-2.on.aws/health
```

First request takes 10-15 seconds (cold start). You should see: `{"status":"healthy"}`

**Authorize GitHub** — open browser:
```
https://abc123xyz.lambda-url.us-east-2.on.aws/authorize?session_id=test1




```
Browser: https://YOUR_API_URL/health
Browser: https://YOUR_API_URL/authorize?session_id=test1
F12 > Console > the fetch call to /run

```

+==============
+--------------
+==============

Three steps, all in your browser. Replace `YOUR_URL` with your actual App Runner domain everywhere below.

---

**Test 1 — Check it's alive:**

Open your browser, go to:

```
https://YOUR_URL/health
```

You should see:

```json
{"status":"healthy"}
```

If you see that, the service is running. If you get an error, the deploy isn't done yet or something's wrong.

---

**Test 2 — Authorize GitHub:**

Open your browser, go to:

```
https://YOUR_URL/authorize?session_id=test1
```

What happens:
1. Your browser redirects to GitHub
2. GitHub shows a page saying "Agent-Z wants to access your account"
3. Click **"Authorize"**
4. You get redirected back to your App Runner URL
5. You see JSON like this:

```json
{
  "status": "authorized",
  "session_id": "test1",
  "message": "GitHub authorized! Now POST to /run to use the agent."
}
```

That `session_id` value (`test1`) is what ties your token to your requests. Remember it.

---

**Test 3 — Run the agent:**

You need to send a POST request. Since you have no terminal tools, use your browser's developer console:

1. Open any tab in your browser (can be any website, even a blank tab)
2. Press **F12** on your keyboard — developer tools open
3. Click the **"Console"** tab at the top of the dev tools panel
4. Paste this and press Enter:

```javascript
fetch('https://YOUR_URL/run', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    action: 'org_info',
    target: 'aws',
    session_id: 'test1'
  })
}).then(r => r.json()).then(d => console.log(JSON.stringify(d, null, 2)))
```

**IMPORTANT:** Replace `YOUR_URL` with your actual App Runner domain before pasting.

Wait a few seconds. You'll see the response printed in the console:

```json
{
  "status": "complete",
  "action": "org_info",
  "target": "aws",
  "github_data": {
    "login": "aws",
    "name": "Amazon Web Services",
    "public_repos": 542,
    "recent_repos": [
      {"name": "some-repo", "stars": 1200, "language": "Python"}
    ]
  },
  "bedrock_analysis": "AWS maintains a large GitHub presence with 542 public repositories...",
  "trace": [
    "✅ Scope check passed for 'org_info'",
    "🔑 GitHub token available",
    "📦 GitHub data fetched for org_info/aws",
    "🤖 Bedrock analysis complete"
  ],
  "elapsed_ms": 2340
}
```

The `trace` array shows you every node the agent went through. The `bedrock_analysis` is Claude's summary of the GitHub data.

---

**Try other actions — same process, just change the body:**

List repos for an org:

```javascript
fetch('https://YOUR_URL/run', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    action: 'list_repos',
    target: 'langchain-ai',
    session_id: 'test1'
  })
}).then(r => r.json()).then(d => console.log(JSON.stringify(d, null, 2)))
```

Get user info:

```javascript
fetch('https://YOUR_URL/run', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    action: 'user_info',
    target: 'octocat',
    session_id: 'test1'
  })
}).then(r => r.json()).then(d => console.log(JSON.stringify(d, null, 2)))
```

---

**What the responses mean:**

| `status: "complete"` | Agent finished all 4 nodes successfully |
| `status: "needs_auth"` | You didn't authorize yet — go to `/authorize?session_id=test1` first |
| `status: "rejected"` | AgentCore Identity blocked it — not a GitHub action |
| `github_data` | Raw data from GitHub API |
| `bedrock_analysis` | Claude's summary of that data |
| `trace` | Every agent node that ran, in order |
| `elapsed_ms` | Total time in milliseconds |
| `error` | If something went wrong, this tells you what |

---

**If you get `"needs_auth"`:** Your session expired or you used a different session_id. Go back to Test 2 and authorize again with the same session_id you're using in `/run`.

**If you get `"rejected"`:** The scope check failed. Make sure your `action` is one of `org_info`, `list_repos`, or `user_info`.

**If `bedrock_analysis` is empty but `github_data` has data:** Bedrock model access isn't enabled or the IAM role doesn't have permissions. Check Step 2 (model access) and Step 5 (IAM role) from the deploy guide.


-------









