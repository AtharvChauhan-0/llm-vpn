"""
Integration Guide: Connecting Your LLM Client to LLM-VPN

This guide shows how to integrate the LLM-VPN proxy with various LLM clients.
"""

# =============================================================================
# SETUP: Generic HTTP Proxy Configuration
# =============================================================================

GENERIC_HTTP_PROXY_SETUP = """
Most LLM clients respect standard HTTP proxy environment variables.

UNIX/Linux/macOS:
  export HTTP_PROXY=http://localhost:8080
  export HTTPS_PROXY=http://localhost:8080
  export NO_PROXY=localhost,127.0.0.1

Windows (PowerShell):
  $env:HTTP_PROXY = "http://localhost:8080"
  $env:HTTPS_PROXY = "http://localhost:8080"

Windows (CMD):
  set HTTP_PROXY=http://localhost:8080
  set HTTPS_PROXY=http://localhost:8080
"""

# =============================================================================
# OPENAI PYTHON CLIENT
# =============================================================================

OPENAI_INTEGRATION = """
from openai import OpenAI
import os

# The client will automatically use HTTP_PROXY/HTTPS_PROXY from environment
# Option 1: Set environment variables
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

# Option 2: Pass proxy directly
client = OpenAI(
    api_key="your-api-key",  # Will still route through proxy
    http_client=httpx.Client(
        proxies="http://localhost:8080"
    )
)

# Now all requests are intercepted by LLM-VPN
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hello, world!"}
    ]
)

# Monitor the request
import requests
stats = requests.get("http://localhost:8081/stats").json()
print(stats["statistics"]["total_requests"])
"""

# =============================================================================
# ANTHROPIC CLIENT
# =============================================================================

ANTHROPIC_INTEGRATION = """
from anthropic import Anthropic

# Set proxy environment variables
import os
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

# Create client (will use proxy automatically)
client = Anthropic(api_key="your-api-key")

# Make a request (will be intercepted by LLM-VPN)
message = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

# Check sessions
import requests
sessions = requests.get("http://localhost:8081/sessions").json()
for session in sessions["sessions"]:
    print(f"Session: {session['session_id']}")
    print(f"  Turn index: {session['turn_index']}")
    print(f"  Intent history: {session['intent_history']}")
"""

# =============================================================================
# GOOGLE GENERATIVE AI
# =============================================================================

GOOGLE_INTEGRATION = """
import google.generativeai as genai
import os

# Set proxy before initializing
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

genai.configure(api_key="your-api-key")

# Create model (requests will be proxied)
model = genai.GenerativeModel('gemini-pro')

# Generate content
response = model.generate_content("Hello!")
print(response.text)

# Get statistics
import requests
stats = requests.get("http://localhost:8081/stats").json()
print(f"Total requests: {stats['statistics']['total_requests']}")
print(f"PII hits: {stats['statistics']['pii_hits']}")
"""

# =============================================================================
# MONITORING AND DEBUGGING
# =============================================================================

MONITORING_EXAMPLES = """
# Monitor in Real-Time

import requests
import json
import time

def monitor_proxy():
    while True:
        # Get current statistics
        stats = requests.get("http://localhost:8081/stats").json()
        
        print("\\n" + "="*50)
        print("LLM-VPN Statistics")
        print("="*50)
        
        total = stats["statistics"]["total_requests"]
        print(f"Total Requests: {total}")
        
        # Intent distribution
        intents = stats["statistics"]["intent_distribution"]
        print(f"\\nIntent Distribution:")
        for intent, count in intents.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {intent}: {count} ({pct:.1f}%)")
        
        # Sensitivity distribution
        sens = stats["statistics"]["sensitivity_distribution"]
        print(f"\\nSensitivity Distribution:")
        for level, count in sens.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {level}: {count} ({pct:.1f}%)")
        
        # PII hits
        pii_hits = stats["statistics"]["pii_hits"]
        print(f"\\nPII Hits: {pii_hits}")
        
        # Active sessions
        sessions = stats["statistics"]["session_stats"]["active_sessions"]
        print(f"Active Sessions: {sessions}")
        
        # Average tokens
        avg_tokens = stats["statistics"]["avg_tokens_per_request"]
        print(f"Avg Tokens/Request: {avg_tokens:.1f}")
        
        time.sleep(5)  # Update every 5 seconds

if __name__ == "__main__":
    monitor_proxy()
"""

# =============================================================================
# DEBUGGING: Check Intercepted Requests
# =============================================================================

DEBUG_EXAMPLES = """
# Debug: Get Session Details

import requests

def debug_session(session_id=None):
    if session_id is None:
        # List all sessions
        response = requests.get("http://localhost:8081/sessions")
        sessions = response.json()["sessions"]
        
        if not sessions:
            print("No active sessions")
            return
        
        session_id = sessions[0]["session_id"]
    
    # Get session details
    response = requests.get(f"http://localhost:8081/sessions/{session_id}")
    session = response.json()
    
    print(f"Session: {session['session_id']}")
    print(f"  Turn Index: {session['turn_index']}")
    print(f"  Agent Depth: {session['agent_depth']}")
    print(f"  Created: {session['created_at']}")
    print(f"  Last Active: {session['last_active']}")
    print(f"  Intent History: {session['intent_history']}")
    print(f"  Expired: {session['is_expired']}")

# Run it
debug_session()


# Debug: Check Health

import requests

def check_health():
    try:
        response = requests.get("http://localhost:8081/health")
        if response.status_code == 200:
            print("✓ LLM-VPN Proxy is healthy")
            return True
    except Exception as e:
        print(f"✗ LLM-VPN Proxy is not responding: {e}")
        return False

# Run it
check_health()
"""

# =============================================================================
# TROUBLESHOOTING
# =============================================================================

TROUBLESHOOTING = """
ISSUE: Requests not being intercepted
SOLUTION:
  1. Verify proxy is running: python main.py
  2. Check HTTP_PROXY/HTTPS_PROXY env vars are set
  3. Verify endpoint is in LLM_ENDPOINTS list
  4. Check logs: curl http://localhost:8081/stats

ISSUE: "Connection refused" error
SOLUTION:
  1. Ensure port 8080 is not in use
  2. Check firewall rules
  3. Verify proxy started successfully
  4. Try: python main.py 2>&1 | tail -20

ISSUE: Inspection API not responding
SOLUTION:
  1. Check port 8081 is not in use
  2. Verify uvicorn started (should see in main.py output)
  3. Try: curl http://localhost:8081/health
  4. Restart main.py

ISSUE: "No module named 'cryptography'"
SOLUTION:
  pip install -r requirements.txt

ISSUE: Keys not generated
SOLUTION:
  python setup.py
  # Check that keys/private.pem and keys/public.pem exist

ISSUE: Tests failing
SOLUTION:
  1. Ensure venv is activated
  2. Run: pip install -r requirements.txt
  3. Run: pytest -v
"""

# =============================================================================
# ADVANCED: Custom Classification Rules
# =============================================================================

CUSTOM_CLASSIFICATION = """
# To add custom classification logic:

# Edit classifier.py - add to classify_tier1():

def classify_tier1(body: dict, turn_index: int, agent_depth: int):
    # ... existing rules ...
    
    # Custom rule: Detect LLaMA-specific patterns
    if "llama" in str(body).lower():
        return IntentClass.SYSTEM_PROMPT, 0.8
    
    # Custom rule: Detect research paper analysis
    if "abstract" in str(body).lower() and "method" in str(body).lower():
        return IntentClass.TOOL_CALL, 0.9
    
    # ... rest of code ...
"""

# =============================================================================
# DEPLOYMENT CHECKLIST
# =============================================================================

DEPLOYMENT_CHECKLIST = """
Pre-Deployment:
  [ ] Generate keys: python setup.py
  [ ] Run tests: pytest
  [ ] Verify stats: curl http://localhost:8081/stats
  [ ] Check health: curl http://localhost:8081/health

Deployment:
  [ ] Move keys/private.pem to secure vault (not git)
  [ ] Configure .env with production settings
  [ ] Set LOG_LEVEL=WARNING in production
  [ ] Run behind TLS terminator (nginx)
  [ ] Set up systemd service or supervisor

Monitoring:
  [ ] Export metrics to Prometheus
  [ ] Set up alerts for PII_HITS > threshold
  [ ] Monitor proxy latency (should be < 100ms)
  [ ] Check session cleanup (should not accumulate)

Security:
  [ ] Verify private key permissions: 600
  [ ] Add authentication to inspection API
  [ ] Enable TLS between proxy and gateway
  [ ] Rotate keys periodically
  [ ] Audit logs for suspicious patterns
"""

# =============================================================================
# PERFORMANCE TUNING
# =============================================================================

PERFORMANCE_TUNING = """
For High Throughput:
  1. Adjust SESSION_TIMEOUT_MINUTES if needed
  2. Use tiktoken for accurate token counts
  3. Consider caching classifier results
  4. Run multiple proxy instances behind load balancer

For Low Latency:
  1. Keep Tier 1 enabled (rule-based < 10ms)
  2. Set TIER2_CONFIDENCE_THRESHOLD high (e.g., 0.9)
  3. Use heuristic token estimation (not tiktoken)
  4. Disable PII detection if not needed

For Production:
  1. Use uvicorn with multiple workers
  2. Set up connection pooling
  3. Enable request batching
  4. Use caching for repeated patterns
"""

if __name__ == "__main__":
    print(__doc__)
