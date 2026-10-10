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

## Safe Demonstration Flow

Use this order when demonstrating an existing environment. These checks do
not create experiments or change cluster resources.

1. Start MySQL using your local MySQL installation and confirm that the `.env`
     values point to that instance. The repository does not include a MySQL
     startup script or compose file.
2. Verify the Kubernetes context and existing application deployment:

     ```powershell
     kubectl config current-context
     kubectl get deployment devops-digital-twin
     kubectl get pods -l app=devops-digital-twin
     ```

     The checked-in deployment manifest uses the `devops-digital-twin` name and
     a baseline of 3 desired replicas. Do not apply a manifest as part of this
     read-only demonstration.
3. Verify Prometheus and, when the backend runs on the host, forward its
     service locally:

     ```powershell
     kubectl get deployment prometheus
     kubectl port-forward service/prometheus 9090:9090
     ```

     Keep that command running in its own terminal. The local backend can then
     use the documented default `PROMETHEUS_URL=http://localhost:9090`.
4. Start the FastAPI backend from the repository root:

     ```powershell
     .venv\Scripts\python.exe -m uvicorn app.src.main:app --reload
     ```

5. Start the dashboard from `dashboard/`:

     ```powershell
     npm run dev
     ```

Open `http://localhost:5173`, use `#experiments` to inspect existing records,
and open an experiment that is in `CREATED` status. Execute is enabled only for
`CREATED` experiments and requires the service name. After execution completes,
the details page refreshes and shows the persisted execution result, simulated
impact, predicted demand, and bottleneck information. Validate is enabled only
for `EXECUTED` experiments; after validation, inspect the actual Kubernetes
result and prediction-versus-actual comparison, then review deployment impact
and recommendations.

Before a scaling demonstration, record the current replica values. After the
workflow, verify the deployment against the checked-in baseline without
performing a scale operation from this guide:

```powershell
kubectl get deployment devops-digital-twin -o jsonpath='{.spec.replicas}{"\n"}'
kubectl get deployment devops-digital-twin -o jsonpath='{.status.readyReplicas}{"\n"}'
```

Saved experiment results come from MySQL through the experiment result APIs.
They are not live infrastructure telemetry. The Infrastructure page remains
honest about the absence of a suitable current Kubernetes/monitoring API.

### Troubleshooting

- If the dashboard cannot reach the API, check `http://localhost:8000/health`
    and confirm `VITE_API_BASE_URL` matches the backend origin. The backend CORS
    configuration allows the local Vite origins `http://localhost:5173` and
    `http://127.0.0.1:5173`.
- If experiments cannot load, verify MySQL is running and that the `MYSQL_*`
    values in `.env` match the database. The dashboard does not contain local
    experiment records.
- If execution cannot collect infrastructure state, verify
    `kubectl config current-context`, the `devops-digital-twin` deployment, and
    the Prometheus port-forward. Check that `PROMETHEUS_URL` points to the
    reachable Prometheus address.
- If an experiment has no result, confirm it has reached `EXECUTED` or
    `VALIDATED` status. Results and comparisons are loaded only when the
    corresponding persisted records exist.
- If the Infrastructure page reports unavailable telemetry, that is expected
    with the current API surface; `/metrics` exposes application metrics but is
    not a dashboard endpoint for live Kubernetes state.

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