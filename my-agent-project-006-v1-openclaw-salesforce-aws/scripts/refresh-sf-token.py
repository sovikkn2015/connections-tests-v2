#!/usr/bin/env python3
"""Refresh Salesforce access token on CRM Lambda and AgentCore runtime."""
import json
import subprocess
import sys
from datetime import datetime

def get_sf_token():
    r = subprocess.run(['sf', 'org', 'display', '--target-org', 'new-org', '--json'], 
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: sf org display failed: {r.stderr[:200]}")
        sys.exit(1)
    return json.loads(r.stdout)['result']['accessToken']

def update_crm_lambda(token):
    r = subprocess.run([
        'aws', 'lambda', 'update-function-configuration',
        '--function-name', 'openclaw-mcp-006-salesforce-crm',
        '--environment', json.dumps({'Variables': {
            'SF_INSTANCE_URL': 'https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com',
            'SF_ACCESS_TOKEN': token,
            'CORS_ALLOW_ORIGIN': 'https://d5n93zwamizsc.cloudfront.net',
        }}),
        '--region', 'us-east-1',
    ], capture_output=True, text=True)
    return r.returncode == 0

def update_agentcore(token):
    # Get current runtime config
    r = subprocess.run([
        'aws', 'bedrock-agentcore-control', 'get-agent-runtime',
        '--agent-runtime-id', 'fsi_research_agent-Sr1m3j3MUh',
        '--region', 'us-east-1',
    ], capture_output=True, text=True)
    if r.returncode != 0:
        return False
    runtime = json.loads(r.stdout)
    env_vars = runtime['environmentVariables']
    env_vars['SF_ACCESS_TOKEN'] = token

    cmd = [
        'aws', 'bedrock-agentcore-control', 'update-agent-runtime',
        '--agent-runtime-id', 'fsi_research_agent-Sr1m3j3MUh',
        '--agent-runtime-artifact', json.dumps(runtime['agentRuntimeArtifact']),
        '--role-arn', runtime['roleArn'],
        '--network-configuration', json.dumps({'networkMode': 'PUBLIC'}),
        '--environment-variables', json.dumps(env_vars),
        '--region', 'us-east-1',
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0

if __name__ == '__main__':
    print(f"[{datetime.utcnow().isoformat()}] Refreshing SF token...")
    token = get_sf_token()
    print(f"  Token: {token[:20]}...")

    ok1 = update_crm_lambda(token)
    print(f"  CRM Lambda: {'OK' if ok1 else 'FAILED'}")

    ok2 = update_agentcore(token)
    print(f"  AgentCore: {'OK' if ok2 else 'FAILED'}")

    if ok1 and ok2:
        print("  All refreshed successfully.")
    else:
        print("  WARNING: Some updates failed.")
        sys.exit(1)
