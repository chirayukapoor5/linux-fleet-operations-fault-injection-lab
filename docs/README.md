# Free online demo

The GitHub Pages demo uses the **original browser-based simulation**. It does not contact Linux hosts or the FastAPI service and is safe as a public portfolio illustration.

To publish on GitHub without a credit card: open Repository → Settings → Pages → Build and deployment → Deploy from a branch → `main` → `/docs` → Save. Your Pages URL will normally be `https://chirayukapoor5.github.io/linux-fleet-operations-fault-injection-lab/` once GitHub finishes deploying.

For the **working API backend**, open the repository in GitHub Codespaces using Code → Codespaces → Create codespace on main. The included `.devcontainer` installs the dependencies and starts FastAPI on port 8000. GitHub Codespaces has monthly free usage limits on eligible personal accounts and is not permanent, always-on hosting. Keep port 8000 private; this training app has unauthenticated mutation endpoints.
