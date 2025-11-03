#!/bin/bash
# Extract connection info from GitHub Actions deployment output
# Usage: ./get_connection_info.sh [workflow_run_number]

set -e

REPO="calldatasystems/cdf-stt"
WORKFLOW_NAME="Deploy CDF STT (Vast.ai)"

echo "=========================================="
echo "CDF STT Connection Info Extractor"
echo "=========================================="
echo

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed"
    echo "Install it from: https://cli.github.com/"
    echo
    echo "Or install via:"
    echo "  Ubuntu/Debian: sudo apt install gh"
    echo "  macOS: brew install gh"
    echo "  Windows: winget install --id GitHub.cli"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo "Fetching latest deployment run..."
echo

# Get the latest workflow run
RUN_ID=$(gh run list \
    --repo "$REPO" \
    --workflow "$WORKFLOW_NAME" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId')

if [ -z "$RUN_ID" ]; then
    echo "Error: No workflow runs found"
    exit 1
fi

echo "Found run ID: $RUN_ID"
echo

# Get the run status
STATUS=$(gh run view "$RUN_ID" --repo "$REPO" --json status --jq '.status')
CONCLUSION=$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq '.conclusion')

echo "Status: $STATUS"
echo "Conclusion: $CONCLUSION"
echo

if [ "$STATUS" != "completed" ]; then
    echo "Warning: Deployment is still $STATUS"
    echo "Wait for it to complete before using connection info"
    echo
fi

if [ "$CONCLUSION" != "success" ] && [ "$CONCLUSION" != "null" ]; then
    echo "Warning: Deployment $CONCLUSION"
    echo "Check logs: gh run view $RUN_ID --repo $REPO --log"
    exit 1
fi

echo "Extracting connection information..."
echo

# Get logs and extract connection info
LOG_OUTPUT=$(gh run view "$RUN_ID" --repo "$REPO" --log 2>/dev/null || echo "")

# Extract instance ID
INSTANCE_ID=$(echo "$LOG_OUTPUT" | grep -oP "Instance created with ID: \K\d+" | tail -1)

# Extract connection details
PUBLIC_IP=$(echo "$LOG_OUTPUT" | grep -oP "Public IP: \K[^\s]+" | tail -1)
SSH_HOST=$(echo "$LOG_OUTPUT" | grep -oP "SSH Host: \K[^\s]+" | tail -1)
SSH_PORT=$(echo "$LOG_OUTPUT" | grep -oP "SSH Port: \K\d+" | tail -1)

# Display results
echo "=========================================="
echo "CONNECTION INFORMATION"
echo "=========================================="
echo

if [ -n "$INSTANCE_ID" ]; then
    echo "Instance ID: $INSTANCE_ID"
else
    echo "Instance ID: Not found in logs"
fi

if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "unknown" ]; then
    echo "Public IP: $PUBLIC_IP"
else
    echo "Public IP: Check Vast.ai console"
fi

if [ -n "$SSH_HOST" ] && [ "$SSH_HOST" != "unknown" ]; then
    echo "SSH Host: $SSH_HOST"
else
    echo "SSH Host: Check Vast.ai console"
fi

if [ -n "$SSH_PORT" ] && [ "$SSH_PORT" != "unknown" ]; then
    echo "SSH Port: $SSH_PORT"
else
    echo "SSH Port: Check Vast.ai console"
fi

echo
echo "=========================================="
echo "NEXT STEPS"
echo "=========================================="
echo

echo "1. Get forwarded port for 8000 from Vast.ai console:"
echo "   https://vast.ai/console/instances/"
echo

if [ -n "$SSH_HOST" ] && [ -n "$SSH_PORT" ] && [ "$SSH_HOST" != "unknown" ] && [ "$SSH_PORT" != "unknown" ]; then
    echo "2. SSH to instance:"
    echo "   ssh -p $SSH_PORT root@$SSH_HOST"
    echo
    echo "3. Or create SSH tunnel for local testing:"
    echo "   ssh -p $SSH_PORT -L 8000:localhost:8000 root@$SSH_HOST"
    echo "   Then access: http://localhost:8000"
    echo
fi

echo "4. Test the API:"
if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "unknown" ]; then
    echo "   curl http://$PUBLIC_IP:FORWARDED_PORT/health"
else
    echo "   curl http://VAST_HOST:FORWARDED_PORT/health"
fi
echo

echo "5. View API docs:"
if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "unknown" ]; then
    echo "   http://$PUBLIC_IP:FORWARDED_PORT/docs"
else
    echo "   http://VAST_HOST:FORWARDED_PORT/docs"
fi
echo

echo "Note: FORWARDED_PORT is shown in Vast.ai console next to port 8000"
echo

echo "=========================================="
echo "ALTERNATIVE: Check Vast.ai Console"
echo "=========================================="
echo
echo "If connection info not found above:"
echo "1. Go to: https://vast.ai/console/instances/"
echo "2. Find instance labeled: cdf-stt-prod"
echo "3. Look for port mapping: 8000 -> XXXXX"
echo "4. Use the displayed connection URL"
echo
