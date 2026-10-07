"""
run_all.py — starts every REACH service (and optionally the frontends).

  python run_all.py              # 6 backend APIs + 2 Next.js apps
  python run_all.py --backend    # backend APIs only
  python run_all.py --fresh      # wipe the local dev database first

Ctrl+C stops everything.
"""
import os, subprocess, sys, time, signal, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

BACKENDS = [
    ("pricing-service",    8001),
    ("generator-service",  8002),
    ("collector-service",  8003),
    ("pickup-service",     8004),
    ("data-layer-service", 8005),
    ("corporate-service",  8006),
]
FRONTENDS = [("generator", 3001), ("collector", 3002)]


def load_env():
    env = os.environ.copy()
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def main():
    backend_only = "--backend" in sys.argv
    env = load_env()
    db_path = os.path.join(ROOT, "reach_dev.db")
    if "--fresh" in sys.argv and os.path.exists(db_path):
        os.remove(db_path)
        print("Removed old dev database")

    procs = []
    try:
        for name, port in BACKENDS:
            src = os.path.join(ROOT, "backend", name, "src")
            p = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--app-dir", src],
                cwd=ROOT, env=env,
            )
            procs.append((name, p))
            print(f"started {name:20s} http://localhost:{port}/docs")
            time.sleep(1.0)  # stagger so SQLite table creation doesn't race

        if not backend_only:
            if shutil.which("npm") is None:
                print("npm not found — skipping frontends (install Node.js 18+)")
            else:
                for app, port in FRONTENDS:
                    cwd = os.path.join(ROOT, "frontend", "apps", app)
                    p = subprocess.Popen(["npm", "run", "dev"], cwd=cwd, env=env, shell=(os.name == "nt"))
                    procs.append((f"{app}-app", p))
                    print(f"started {app+'-app':20s} http://localhost:{port}")

        print("\nEverything is up. Ctrl+C to stop.\n")
        while True:
            time.sleep(1)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"!! {name} exited with code {p.returncode}")
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for name, p in procs:
            if p.poll() is None:
                p.terminate()
        for name, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
