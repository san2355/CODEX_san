# Single Colab cell (copy/paste): run latest telemonitoring Streamlit app from this repo + public URL
# Keeps app code in sync by cloning repo and launching app.py directly.

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = "https://github.com/san2355/CODEX_san.git"
BRANCH = "main"  # change if needed
APP_FILE = "app.py"
WORKDIR = Path("/content/CODEX_san")

# 1) Install dependencies
subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "-q",
    "streamlit",
    "streamlit-autorefresh",
    "pandas",
    "numpy",
    "plotly",
])

# 2) Fresh clone
if WORKDIR.exists():
    shutil.rmtree(WORKDIR)

subprocess.check_call([
    "git",
    "clone",
    "--depth",
    "1",
    "--branch",
    BRANCH,
    REPO_URL,
    str(WORKDIR),
])

assert (WORKDIR / APP_FILE).exists(), f"Missing {APP_FILE} in cloned repository"

# 3) Install cloudflared for public tunnel (no ngrok)
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.check_call([
        "wget",
        "-q",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "-O",
        "/usr/local/bin/cloudflared",
    ])
    subprocess.check_call(["chmod", "+x", "/usr/local/bin/cloudflared"])

# 4) Start Streamlit app
subprocess.run(["pkill", "-f", "streamlit run app.py"], check=False)

streamlit_cmd = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    APP_FILE,
    "--server.port",
    "8501",
    "--server.address",
    "0.0.0.0",
    "--server.headless",
    "true",
    "--browser.gatherUsageStats",
    "false",
]
st_proc = subprocess.Popen(
    streamlit_cmd,
    cwd=str(WORKDIR),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# 5) Start Cloudflare tunnel
cf_proc = subprocess.Popen(
    ["/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8501"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# 6) Detect and print public URL
public_url = None
pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com", re.I)
start = time.time()

while time.time() - start < 45 and public_url is None:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    m = pattern.search(line)
    if m:
        public_url = m.group(0)
        break

if public_url:
    print("\n✅ Telemonitoring app is live:")
    print(public_url)
    print("\nTip: keep this cell running while you test the longitudinal patient analysis view.")
else:
    print("\n⚠️ Tunnel URL not detected yet. Recent tunnel output:")
    for _ in range(30):
        line = cf_proc.stdout.readline()
        if not line:
            break
        print(line.rstrip())
