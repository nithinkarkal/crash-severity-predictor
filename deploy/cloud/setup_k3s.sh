#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-time cluster bootstrap. Run ON the Oracle Ampere (Ubuntu, ARM64) VM.
#   - opens the host firewall for 80/443 (Oracle Ubuntu blocks these by default)
#   - installs k3s WITHOUT Traefik (we use ingress-nginx to match the project)
#   - installs ingress-nginx (k3s's built-in ServiceLB binds host 80/443)
#   - installs cert-manager (for Let's Encrypt TLS)
#
# Usage:
#   chmod +x setup_k3s.sh && ./setup_k3s.sh
# ---------------------------------------------------------------------------
set -euo pipefail

INGRESS_NGINX_VER="controller-v1.11.3"
CERT_MANAGER_VER="v1.16.2"

echo "== [1/5] Opening host firewall for 80/443 =="
# Oracle Ubuntu images ship iptables rules that only allow 22. Insert ACCEPTs
# ABOVE the default REJECT, then persist them.
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
sudo netfilter-persistent save
echo "   (Also open 80 + 443 (Ingress: TCP, source 0.0.0.0/0) in the Oracle Cloud"
echo "    Console -> your VCN -> Security List / NSG. The cloud firewall is separate.)"

echo "== [2/5] Installing k3s (no Traefik) =="
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik --write-kubeconfig-mode 644" sh -

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> "$HOME/.bashrc"

echo "== [3/5] Waiting for the node to be Ready =="
until kubectl get nodes 2>/dev/null | grep -q " Ready "; do sleep 3; done
kubectl get nodes

echo "== [4/5] Installing ingress-nginx ($INGRESS_NGINX_VER) =="
kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VER}/deploy/static/provider/cloud/deploy.yaml"
echo "   waiting for the ingress controller ..."
# rollout status waits for the Deployment (handles the brief window before pods appear,
# unlike `kubectl wait pod` which errors with 'no matching resources found').
kubectl rollout status deploy/ingress-nginx-controller -n ingress-nginx --timeout=300s

echo "== [5/5] Installing cert-manager ($CERT_MANAGER_VER) =="
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VER}/cert-manager.yaml"
echo "   waiting for cert-manager ..."
kubectl rollout status deploy/cert-manager -n cert-manager --timeout=300s
kubectl rollout status deploy/cert-manager-webhook -n cert-manager --timeout=300s

echo ""
echo "Cluster ready. Next: run deploy/cloud/deploy.sh (see deploy/cloud/DEPLOY.md)."
echo "Find the public IP that ingress bound:"
kubectl get svc -n ingress-nginx ingress-nginx-controller -o wide || true
