# DevOps Digital Twin

A DevOps-focused Digital Twin system for infrastructure simulation,
what-if analysis, resource prediction, failure simulation, and deployment
impact analysis. The repository contains a FastAPI backend and a React/Vite
dashboard backed by MySQL for persisted experiments and results.

## Technology Stack

- Python 3.13, FastAPI, Uvicorn, pytest
- React, TypeScript, Vite
- MySQL
- Docker, Jenkins, Kubernetes, Prometheus

## Backend Setup

Create a virtual environment and install the backend dependencies from the
repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
```

Copy the environment template and replace the placeholder MySQL password with
your local value. Do not commit `.env`:

```powershell
Copy-Item .env.example .env
```

The backend reads these configuration values:

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `PROMETHEUS_URL` (default: `http://localhost:9090`)
- `KUBERNETES_DEPLOYMENT_NAME` (default: `devops-digital-twin`)
- `KUBERNETES_NAMESPACE` (default: `default`)

Start the API from the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn app.src.main:app --reload
```

The API is available at `http://localhost:8000`. Its read-only dashboard
routes include `/health`, `/experiments`,
`/experiments/{experiment_id}/result`,
`/experiments/{experiment_id}/impact`, and
`/experiments/{experiment_id}/recommendations`. `/metrics` exposes the
application's Prometheus-format metrics.

## Dashboard Setup

From `dashboard/`:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. The dashboard client defaults to
`http://localhost:8000`; use `VITE_API_BASE_URL` when the API runs elsewhere:

```powershell
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

The dashboard uses hash navigation for these pages:

- `#dashboard`: experiment counts and recent experiment records
- `#experiments`: ordered experiment list with links to details
- `#experiment/{id}`: metadata, lifecycle actions, execution result, impact,
  and recommendations
- `#results`: persisted execution results and validated prediction comparisons
- `#infrastructure`: reports the current telemetry API limitation

Execute is available for experiments in `CREATED` status. Validate is
available for experiments in `EXECUTED` status. Both actions require the
backend and refresh the relevant persisted data after success.

## Infrastructure and Monitoring Limitations

The backend has an application health endpoint and exposes application
metrics, but it does not provide a suitable read-only dashboard endpoint for
current Kubernetes deployment state or monitoring connection status. The
Infrastructure page therefore does not display fabricated replica, CPU,
memory, health, or Prometheus connection values.

Execution and validation workflows that use real infrastructure require a
working MySQL database, a configured Kubernetes context and deployment, and a
reachable Prometheus instance matching `PROMETHEUS_URL`. The dashboard alone
does not provision these services.

## Tests and Checks

Run the backend test suite from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Run dashboard checks from `dashboard/`:

```powershell
npm run build
npm run lint
```