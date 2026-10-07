"""
install_all.py — one-time setup. Installs Python deps and both Next.js apps.
Usage:  python install_all.py
(Run inside an activated virtualenv if you use one — see README.)
"""
import subprocess, sys, os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

def run(cmd, cwd=ROOT):
    print(f"\n$ {' '.join(cmd)}   (in {os.path.relpath(cwd, ROOT) or '.'})")
    subprocess.check_call(cmd, cwd=cwd, shell=(os.name == "nt" and cmd[0] == "npm"))

run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

if not os.path.exists(os.path.join(ROOT, ".env")):
    shutil.copy(os.path.join(ROOT, ".env.example"), os.path.join(ROOT, ".env"))
    print("Created .env from .env.example (placeholder values — edit later)")

if shutil.which("npm") is None:
    sys.exit("npm not found — install Node.js 18+ from https://nodejs.org then re-run.")

for app in ("generator", "collector"):
    run(["npm", "install", "--no-audit", "--no-fund"], cwd=os.path.join(ROOT, "frontend", "apps", app))

print("\nAll dependencies installed. Next:  python run_all.py")
