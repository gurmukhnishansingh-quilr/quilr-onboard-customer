# Quilr Onboarding Portal

Customer onboarding portal with Microsoft OAuth, instance CRUD, and a FastAPI backend.

## Structure
- `backend/` FastAPI service (SQLite storage, Microsoft OAuth, CRUD APIs)
- `frontend/` Next.js UI (login, onboarding, instance management)
- `scripts/` Python onboarding helper

## Backend setup
1. Copy `backend/.env.example` to `backend/.env` and update the values.
2. Create a virtual env and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. Run the API:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```

## Frontend setup
1. Copy `frontend/.env.local.example` to `frontend/.env.local` if needed.
2. Install packages and run:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## OAuth notes
- Set `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`, and `MS_REDIRECT_URI` in `backend/.env`.
- `DEV_AUTH_BYPASS=true` allows local development without Microsoft login.

## API endpoints
- `GET /api/instances`
- `POST /api/instances`
- `PUT /api/instances/{id}`
- `DELETE /api/instances/{id}`
- `GET /api/customers`
- `POST /api/customers`
- `PUT /api/customers/{id}`
- `DELETE /api/customers/{id}`
- `POST /api/onboard` (creates instance + customer)

## Onboarding script
The helper script calls the API for onboarding flows.

```bash
pip install -r scripts/requirements.txt
```

```bash
python scripts/onboard_customer.py \
  --customer-name "Acme" \
  --contact-email "admin@acme.io" \
  --instance-name "Acme US" \
  --instance-region "US-East"
```

If you are using `DEV_AUTH_BYPASS=true`, the script can call the API without OAuth.

## MicroK8s deployment
1. Enable required addons:
   ```bash
   microk8s enable dns storage ingress registry
   ```
2. Build and push images to the local registry:
   ```bash
   docker build -t localhost:32000/quilr-onboard-backend:latest -f backend/Dockerfile .
   docker build \
     --build-arg NEXT_PUBLIC_API_BASE_URL=http://quilr.local \
     -t localhost:32000/quilr-onboard-frontend:latest \
     -f frontend/Dockerfile .
   docker push localhost:32000/quilr-onboard-backend:latest
   docker push localhost:32000/quilr-onboard-frontend:latest
   ```
3. Update `k8s/configmap.yaml` and `k8s/secret.yaml` with real values.
4. Apply the manifests:
   ```bash
   microk8s kubectl apply -f k8s
   ```
5. Map `quilr.local` to your node IP (example):
   ```bash
   sudo sh -c 'echo "127.0.0.1 quilr.local" >> /etc/hosts'
   ```
6. Open `http://quilr.local` in the browser.

Notes:
- Microsoft OAuth redirect URI must match `http://quilr.local/auth/callback`.
- If you change the host name, rebuild the frontend with the new `NEXT_PUBLIC_API_BASE_URL`.
