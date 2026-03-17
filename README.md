copy C:\afp-py-test-br\app.py C:\afp-py-test-br\package\app.py
cd C:\afp-py-test-br\package
del C:\afp-py-test-br\agent-afp-py-test-br.zip
tar -a -cf C:\afp-py-test-br\agent-z.zip *
cd C:\afp-py-test-br
```

Now continue in the AWS Console. Every step below is clicking in your browser.

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

## STEP 7: Create Function URL

1. Still on Configuration tab
2. Left side > click **"Function URL"**
3. Click **"Create function URL"**
4. Auth type: **NONE**
5. Click **"Save"**
6. You'll see a URL appear like:
```
https://abc123xyz.lambda-url.us-east-2.on.aws
```

7. Copy this URL

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
