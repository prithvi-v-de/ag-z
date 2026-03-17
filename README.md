Here's every click. You'll launch an EC2 instance, build the image, push to ECR, terminate the instance, then create App Runner from the image.

---

## STEP 1: Create ECR Repository (2 min)

1. AWS Console > make sure **Ohio (us-east-2)** top-right
2. Search **"ECR"** > click **"Elastic Container Registry"**
3. Click **"Create repository"**
4. Visibility: **Private**
5. Repository name: `agent-z`
6. Click **"Create repository"**

---

## STEP 2: Add a Dockerfile to your GitHub repo (1 min)

Go to your repo on GitHub > Add file > Create new file

Filename: `Dockerfile`

Paste:

```
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
EXPOSE 8080
CMD ["gunicorn","--bind","0.0.0.0:8080","--workers","2","--timeout","120","app:app"]
```

Commit.

(If `requirements.txt` is in your root instead of `backend/`, change the COPY line to `COPY requirements.txt .` instead)

---

## STEP 3: Launch EC2 Instance (5 min)

1. AWS Console > search **"EC2"** > click it
2. Click **"Launch instance"**

**Name:**

3. Name: `build-machine`

**AMI (operating system):**

4. Keep the default **Amazon Linux 2023** (should already be selected)

**Instance type:**

5. Select **t3.micro** (or `t2.micro` if t3 isn't available — both are free tier)

**Key pair:**

6. Click **"Proceed without a key pair"** — you don't need one because you'll connect via browser

**Network settings:**

7. Click **"Edit"** next to Network settings
8. Make sure **"Auto-assign public IP"** is set to **Enable**
9. Under security group, keep the default or create new — doesn't matter, you're connecting via Instance Connect not SSH

**Storage:**

10. Change the root volume to **20 GB** (the default 8 GB is too small for Docker builds)

11. Click **"Launch instance"**
12. Click **"View all instances"**
13. Wait until the **"Instance state"** column shows **"Running"** and **"Status check"** shows **"2/2 checks passed"** (takes 1-2 minutes)

---

## STEP 4: Connect to the Instance (1 min)

1. Check the box next to your `build-machine` instance
2. Click **"Connect"** button at the top
3. You'll see a "Connect to instance" page
4. Select the **"EC2 Instance Connect"** tab
5. Leave the username as `ec2-user`
6. Click **"Connect"**
7. A **black terminal** opens in your browser — you're in

---

## STEP 5: Build and Push Image (10 min)

Type these commands **one at a time** in the browser terminal. Press Enter after each.

**Install Docker:**

```bash
sudo yum install -y docker
```

```bash
sudo service docker start
```

```bash
sudo usermod -aG docker ec2-user
```

```bash
newgrp docker
```

Verify Docker works:

```bash
docker --version
```

Should show something like `Docker version 25.x.x`. If yes, continue.

**Install Git:**

```bash
sudo yum install -y git
```

**Clone your repo:**

```bash
git clone https://github.com/YOUR_USERNAME/Agent-Z.git
```

(Replace `YOUR_USERNAME` with your actual GitHub username. If the repo is private, it'll ask for username and password — for password, use a GitHub Personal Access Token from github.com/settings/tokens)

```bash
cd Agent-Z
```

**Verify your files are there:**

```bash
ls -la
```

You should see `Dockerfile`, `backend/`, `README.md`, etc.

**Get your AWS account ID:**

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "Account: $ACCOUNT"
```

This should print your 12-digit account number. If it does, continue.

**Log Docker into ECR:**

```bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com
```

Should say **"Login Succeeded"**.

**Build the image:**

```bash
docker build -t agent-z .
```

Wait 1-2 minutes. It'll download Python, install your requirements. When you see `Successfully tagged agent-z:latest`, it's done.

**Tag it for ECR:**

```bash
docker tag agent-z:latest $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com/agent-z:latest
```

**Push it:**

```bash
docker push $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com/agent-z:latest
```

Wait 1-2 minutes. When you see `latest: digest: sha256:...` — it's done. Your image is in ECR.

---

## STEP 6: Terminate the EC2 Instance (1 min)

You don't need it anymore. Kill it so you stop paying.

1. Go back to your AWS Console tab
2. Search **"EC2"** > click **"Instances"**
3. Check the box next to `build-machine`
4. Click **"Instance state"** dropdown (top right)
5. Click **"Terminate instance"**
6. Confirm

Gone. Cost you about 1-2 cents.

---

## STEP 7: Create IAM Role for App Runner (5 min)

(Skip if you already created `AgentZBedrockRole` earlier)

1. AWS Console > search **"IAM"** > click it
2. Left sidebar > **"Roles"** > **"Create role"**
3. Select **"Custom trust policy"**
4. Delete everything, paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "tasks.apprunner.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

5. Click **"Next"**
6. Search `AmazonBedrockFullAccess` > check it
7. Click **"Next"**
8. Role name: `AgentZBedrockRole`
9. Click **"Create role"**

---

## STEP 8: Create App Runner Service (10 min)

1. AWS Console > search **"App Runner"** > make sure **Ohio (us-east-2)**
2. Click **"Create service"**

**Page 1 — Source:**

3. Source: **"Container registry"**
4. Provider: **"Amazon ECR"**
5. Click **"Browse"** > find **agent-z** > select tag **latest**
6. Deployment trigger: **Manual**
7. ECR access role: **"Create new service role"**
8. Click **"Next"**

**Page 2 — Configure:**

9. Service name: `agent-z`
10. CPU: **1 vCPU**
11. Memory: **2 GB**
12. Port: `8080`

13. Scroll to **"Environment variables"** — add 7:

| Key | Value |
|-----|-------|
| `AWS_REGION` | `us-east-2` |
| `GITHUB_AGENT_IDENTITY_ARN` | your ARN from notepad |
| `GITHUB_CLIENT_ID` | from notepad |
| `GITHUB_CLIENT_SECRET` | from notepad |
| `APP_URL` | `https://placeholder` |
| `FLASK_SECRET_KEY` | `anyrandomtext123` |
| `BEDROCK_MODEL_ID` | `anthropic.claude-haiku-4-5-20251001-v1:0` |

14. Instance role: select **AgentZBedrockRole**  (refresh if you don't see it)
15. Click **"Next"**

**Page 3 — Health check:**

16. Protocol: **HTTP**
17. Path: `/health`
18. Click **"Next"**

**Page 4 — Review:**

19. Click **"Create & deploy"**
20. Wait 3-5 min until status shows **"Running"**

---

## STEP 9: Update URLs (3 min)

Copy your App Runner domain from the top of the service page.

**9a. Update APP_URL in App Runner:**
- Configuration tab > Edit
- Change `APP_URL` to: `https://YOUR_DOMAIN.us-east-2.awsapprunner.com` (NO trailing space)
- Save > wait for redeploy

**9b. Update GitHub OAuth callback:**
- github.com/settings/developers > your app
- Change callback to: `https://YOUR_DOMAIN.us-east-2.awsapprunner.com/callback`
- Change homepage too
- Update application

---

## STEP 10: Test It

1. Browser: `https://YOUR_URL/health` → `{"status":"healthy"}`
2. Browser: `https://YOUR_URL/authorize?session_id=test1` → authorize on GitHub
3. F12 > Console > paste:

```javascript
fetch('https://YOUR_URL/run', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({action:'org_info', target:'aws', session_id:'test1'})
}).then(r=>r.json()).then(d=>console.log(JSON.stringify(d,null,2)))
```

---

## REDEPLOYING AFTER CODE CHANGES

Same EC2 trick — but faster since Docker is cached:

1. Launch another `t3.micro` (or keep one running if you're iterating)
2. Connect via Instance Connect
3. Run:

```bash
sudo yum install -y docker git
sudo service docker start
sudo usermod -aG docker ec2-user
newgrp docker
git clone https://github.com/YOUR_USERNAME/Agent-Z.git
cd Agent-Z
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com
docker build -t agent-z .
docker tag agent-z:latest $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com/agent-z:latest
docker push $ACCOUNT.dkr.ecr.us-east-2.amazonaws.com/agent-z:latest
```

4. Terminate the instance
5. App Runner console > your service > Actions > **"Deploy"**
