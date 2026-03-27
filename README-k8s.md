# Deploying to k3s

## Prerequisites

- k3s cluster running and accessible
- `kubectl` configured locally
- `helm` v3 installed
- GitHub repo with Actions enabled
- Images will be pushed to **GHCR** (GitHub Container Registry) — no extra registry needed

---

## 1. Secrets (external-first)

This chart is now external-secret-first:

- `backend.createSecret=false` by default
- `postgres.createSecret=false` by default

Create both required secrets before install:

```bash
kubectl create namespace steam-roulette --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=your_key_here \
  --from-literal=METRICS_TOKEN=your_metrics_token \
  -n steam-roulette

kubectl create secret generic steam-roulette-postgres-secret \
  --from-literal=POSTGRES_DB=steamroulette \
  --from-literal=POSTGRES_USER=steamroulette \
  --from-literal=POSTGRES_PASSWORD=strong_password_here \
  --from-literal=DATABASE_URL='postgresql://steamroulette:strong_password_here@steam-roulette-postgres:5432/steamroulette' \
  -n steam-roulette
```

You can still let Helm create secrets by setting:

```yaml
backend:
  createSecret: true
postgres:
  createSecret: true
```

---

## 2. Helm values

Edit `helm/steam-roulette/values.yaml` before first deploy:

```yaml
image:
  repository: yourname/steam-roulette   # your GitHub username/org

ingress:
  host: steam-roulette.yourdomain.com   # your actual domain or local hostname

postgres:
  enabled: true
  backup:
    enabled: true
    schedule: "0 */6 * * *"
    retentionDays: 7
```

### TLS with cert-manager (optional)

If you have cert-manager installed on your cluster:

```yaml
ingress:
  tls:
    enabled: true
    secretName: steam-roulette-tls
```

---

## 3. Manual deploy (first time or local)

```bash
# Install chart
helm upgrade --install steam-roulette ./helm/steam-roulette \
  --namespace steam-roulette \
  --set image.repository=yourname/steam-roulette \
  --wait
```

On install/upgrade, a DB migration job runs before workloads (`pre-install,pre-upgrade` Helm hook).

---

## 4. Backup and restore

If `postgres.backup.enabled=true`, the chart creates:

- a backup PVC: `steam-roulette-postgres-backup-pvc`
- a CronJob: `steam-roulette-postgres-backup`

Backups are gzipped SQL dumps in `/backups` and old files are pruned via `retentionDays`.

Example restore:

```bash
kubectl -n steam-roulette exec -it statefulset/steam-roulette-postgres -- sh

# inside the pod:
export PGPASSWORD="$POSTGRES_PASSWORD"
gunzip -c /backups/steamroulette-YYYYMMDDHHMMSS.sql.gz | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

---

## 5. Useful commands

```bash
# Check pod status
kubectl get pods -n steam-roulette

# Tail backend logs
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette

# Migration job logs
kubectl logs -f job/steam-roulette-db-migrate -n steam-roulette

# Tail frontend logs
kubectl logs -f deployment/steam-roulette-frontend -n steam-roulette

# Postgres logs
kubectl logs -f statefulset/steam-roulette-postgres -n steam-roulette

# Uninstall
helm uninstall steam-roulette -n steam-roulette

# Lint the chart
helm lint ./helm/steam-roulette
```
