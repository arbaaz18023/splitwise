import os
import subprocess
import sys

token = os.environ.get("GITHUB_TOKEN")
if not token:
    print("ERROR: GITHUB_TOKEN secret is not set.")
    sys.exit(1)

remote_url = f"https://arbaaz18023:{token}@github.com/arbaaz18023/splitwise.git"
branch = "dev"

print(f"Pushing to branch: {branch}")
result = subprocess.run(
    ["git", "push", remote_url, f"HEAD:{branch}"],
    capture_output=True,
    text=True,
)
print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
