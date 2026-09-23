# Homelab Compose Stack

## About
This repository is a curated collection of Docker Compose configurations for a variety of self-hosted services, for personal use. Rather than relying on fragmented documentation, this serves as a centralized source of truth for a stable, personalized homelab environment, enabling rapid redeployment and consistent configuration across a full suite of services.

## Technical Details
The repository utilizes a modular directory structure where each service is isolated in its own folder. Each directory contains a `docker-compose.yml` file specifying the precise image versions, environment variables, and volume mounts required for that service. This architecture avoids the complexity of a single monolithic compose file, allowing for independent scaling and updates.

The stack covers several domains of self-hosting:
- Network & Security: Pi-hole, Cloudflare
- Media & Content: Jellyfin
- Automation & Development: n8n, Gitea, Github-Runner
- AI & LLMs: Ollama, Open WebUI, Speaches
- Infrastructure & Monitoring: Portainer, Scrutiny, Librespeed, Glance

## Execution
To deploy a specific service, navigate to its corresponding directory and use Docker Compose:

```bash
cd <service-name>
docker compose up -d
```

To restart the primary services in bulk, you can execute the provided helper script from the root directory:

```bash
chmod +x restart_all.sh
./restart_all.sh
```