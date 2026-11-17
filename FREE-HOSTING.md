# Deploy FleetOps without a credit card

## A. Public GitHub Pages demo (free static simulation)

The `docs/index.html` file is the original standalone HTML simulator. GitHub Pages cannot execute Python/FastAPI, run Docker or store incidents in SQLite. Its browser-based UI uses mock nodes and simulated faults. **Do not label the Pages demo as live infrastructure.**

Enable Pages under **Settings → Pages → Deploy from a branch → main → /docs → Save**. Then visit `https://chirayukapoor5.github.io/linux-fleet-operations-fault-injection-lab/` once published.

## B. Working backend in GitHub Codespaces (free quota on eligible accounts)

Click **Code → Codespaces → Create codespace on main**. `.devcontainer/devcontainer.json` installs requirements and launches `uvicorn` on port 8000. The forwarded dashboard opens in your browser. When stopped, the service stops. GitHub may require billing setup once the free allowance is exhausted, so set a spending limit or avoid any paid use. Keep forwarded port visibility **Private** because the API is not authenticated.

### Run tests

`python -m pytest -q`

## C. Real Linux fault injection

Neither Pages nor a basic Codespace turns the mock nodes into actual machines. A real mode requires isolated Linux VMs or containers, a constrained telemetry agent, authorization, resource guards, and auditable fault execution. Do not expose the current API publicly without authentication and rate limits.
