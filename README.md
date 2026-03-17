# ag-z

Agent-Z/
├── apprunner.yaml              ← app runner build & run
├── README.md                   ← what this is
├── backend/
│   ├── app.py                  ← the entire agent (425 lines)
│   └── requirements.txt        ← python dependencies (7 lines)



Endpoints:
  GET  /authorize?session_id=xxx  → starts GitHub OAuth
  POST /run                       → runs the agent
  GET  /health                    → health check
