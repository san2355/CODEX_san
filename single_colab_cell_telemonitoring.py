# Single Colab cell (copy/paste): run Connected Care telemonitoring dashboard from this branch
# Paste this entire cell into Google Colab and run once.

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = "https://github.com/san2355/CODEX_san.git"
BRANCH = "conected_care_Telemonitoring"  # branch with the refreshed Connected Care dashboard
APP_FILE = "app.py"
WORKDIR = Path("/content/CODEX_san")

# 1) Install runtime dependencies
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "streamlit", "streamlit-autorefresh", "pandas", "numpy", "plotly"
])

# 2) Fresh clone of requested branch
if WORKDIR.exists():
    shutil.rmtree(WORKDIR)
subprocess.check_call([
    "git", "clone", "--depth", "1", "--branch", BRANCH, REPO_URL, str(WORKDIR)
])
assert (WORKDIR / APP_FILE).exists(), f"Missing {APP_FILE}"

# 3) Install cloudflared tunnel helper (for public URL)
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.check_call([
        "wget", "-q",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "-O", "/usr/local/bin/cloudflared"
    ])
    subprocess.check_call(["chmod", "+x", "/usr/local/bin/cloudflared"])

# 4) Start app + tunnel
subprocess.run(["pkill", "-f", "streamlit run app.py"], check=False)
subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", APP_FILE,
    "--server.port", "8501",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false",
], cwd=str(WORKDIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

cf_proc = subprocess.Popen([
    "/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8501"
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

public_url = None
pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com", re.I)
start = time.time()
while time.time() - start < 60 and public_url is None:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    m = pattern.search(line)
    if m:
        public_url = m.group(0)
        break

if public_url:
    print("✅ Connected Care dashboard is live:")
    print(public_url)
    print("\nTip: keep this cell running while testing the Patient Wall, Alerts Summary, and Longitudinal views.")
else:
    print("⚠️ Tunnel URL not detected yet. Re-run the cell or wait a few seconds.")
