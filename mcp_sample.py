# mcp_server.py
import json
from mcp.server.fastmcp import FastMCP
from github_tools import get_repos, get_file, create_pr, get_user
from atlassian_tools import list_projects, get_issue, search_confluence, get_spaces
from validate_terraform import validate
from generate_module import generate
from check_security import check
from parse_requirements import parse
from read_ruleset import read_rules

mcp = FastMCP("iac-tools")

# ---- GITHUB ----
@mcp.tool()
def github_whoami() -> str:
    """Get authenticated GitHub Enterprise user profile"""
    return json.dumps(get_user())

@mcp.tool()
def github_list_repos() -> str:
    """List GitHub Enterprise repositories"""
    return json.dumps(get_repos())

@mcp.tool()
def github_get_file(repo: str, path: str) -> str:
    """Read a file from a GitHub Enterprise repo"""
    return json.dumps(get_file(repo, path))

@mcp.tool()
def github_create_pr(repo: str, branch: str, title: str) -> str:
    """Create a pull request on GitHub Enterprise"""
    return json.dumps(create_pr(repo, branch, title))

# ---- ATLASSIAN ----
@mcp.tool()
def jira_list_projects() -> str:
    """List Jira projects"""
    return json.dumps(list_projects())

@mcp.tool()
def jira_get_issue(issue_key: str) -> str:
    """Get details of a Jira issue"""
    return json.dumps(get_issue(issue_key))

@mcp.tool()
def confluence_get_spaces() -> str:
    """List Confluence spaces"""
    return json.dumps(get_spaces())

@mcp.tool()
def confluence_search(query: str) -> str:
    """Search Confluence content"""
    return json.dumps(search_confluence(query))

# ---- CUSTOM TOOLS ----
@mcp.tool()
def validate_terraform(code: str) -> str:
    """Validate Terraform against policies"""
    return json.dumps(validate(code))

@mcp.tool()
def generate_module(service: str, account_id: str) -> str:
    """Generate hardened Terraform module"""
    return json.dumps(generate(service, account_id))

@mcp.tool()
def check_security_rules(code: str) -> str:
    """Check enterprise security policies"""
    return json.dumps(check(code))

@mcp.tool()
def parse_requirements(ticket_text: str) -> str:
    """Parse Jira ticket into structured requirements"""
    return json.dumps(parse(ticket_text))

@mcp.tool()
def read_ruleset(ruleset_name: str) -> str:
    """Read an engineering ruleset"""
    return json.dumps(read_rules(ruleset_name))

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
