# Deploying to k3s

## Prerequisites

- k3s cluster running and accessible
- `kubectl` configured locally
- `helm` v3 installed
- GitHub repo with Actions enabled
- Images will be pushed to **GHCR** (GitHub Container Registry) — no extra registry needed

---

## 1. Secrets

### GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `KUBECONFIG` | Full contents of your k3s kubeconfig (`/etc/rancher/k3s/k3s.yaml` on the server — replace `127.0.0.1` with your server's IP) |
| `STEAM_API_KEY` | Your Steam Web API key |

The pipeline creates/updates the Kubernetes secret automatically on every deploy — you never commit the key.

---

## 2. Helm values

Edit `helm/steam-roulette/values.yaml` before first deploy:

```yaml
image:
  repository: yourname/steam-roulette   # your GitHub username/org

ingress:
  host: steam-roulette.yourdomain.com   # your actual domain or local hostname
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
# Create namespace
kubectl create namespace steam-roulette

# Create the secret manually
kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=your_key_here \
  --namespace steam-roulette

# Install chart
helm upgrade --install steam-roulette ./helm/steam-roulette \
  --namespace steam-roulette \
  --set image.repository=yourname/steam-roulette \
  --wait
```

---

## 4. CI/CD pipeline

Every push to `main`:

1. Builds both Docker images and pushes to GHCR tagged with `sha-<commit>` and `latest`
2. Writes the kubeconfig to the runner
3. Creates/updates the `steam-roulette-secret` from the GitHub secret
4. Runs `helm upgrade --install` with the new image tags
5. Verifies both deployments roll out successfully

Pull requests only run the build step — no deploy.

---

## 5. Useful commands

```bash
# Check pod status
kubectl get pods -n steam-roulette

# Tail backend logs
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette

# Tail frontend logs
kubectl logs -f deployment/steam-roulette-frontend -n steam-roulette

# Uninstall
helm uninstall steam-roulette -n steam-roulette

# Lint the chart
helm lint ./helm/steam-roulette
```
