# Single Colab cell (copy/paste): run telemonitoring app from repo with Longitudinal Patient Analysis
# This cell clones the latest repo, runs Streamlit app.py, and opens a public Cloudflare URL.

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = "https://github.com/san2355/CODEX_san.git"
BRANCH = "main"
WORKDIR = Path("/content/CODEX_san")
APP_FILE = "app.py"

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "streamlit", "streamlit-autorefresh", "pandas", "numpy", "plotly"])

if WORKDIR.exists():
    shutil.rmtree(WORKDIR)
subprocess.check_call(["git", "clone", "--depth", "1", "--branch", BRANCH, REPO_URL, str(WORKDIR)])
assert (WORKDIR / APP_FILE).exists(), f"Missing {APP_FILE}"

if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.check_call(["wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-O", "/usr/local/bin/cloudflared"])
    subprocess.check_call(["chmod", "+x", "/usr/local/bin/cloudflared"])

subprocess.run(["pkill", "-f", "streamlit run app.py"], check=False)
subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "app.py",
    "--server.port", "8501",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false",
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# 5) Cloudflare tunnel and URL
cf_proc = subprocess.Popen([
    "/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8501"
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

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

url = None
pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com", re.I)
start = time.time()
while time.time() - start < 45 and url is None:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    m = pattern.search(line)
    if m:
        url = m.group(0)
        break

if url:
    print("✅ App live URL:")
    print(url)
    print("\nOpen it and scroll to: 🧭 Longitudinal Patient Analysis")
else:
    print("⚠️ Could not detect tunnel URL yet.")
