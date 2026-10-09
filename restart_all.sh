#!/bin/bash

# cloudflare
echo "Restarting Cloudflare..."
cd cloudflare
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# # frigate
# echo "Restarting Frigate..."
# cd frigate
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# # gitea
# echo "Restarting Gitea..."
# cd gitea
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# # github-runner
# echo "Restarting Github Runner..."
# cd github-runner
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# glance
echo "Restarting Glance..."
cd glance
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# # immich
# echo "Restarting Immich..."
# cd immich
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# jellyfin
echo "Restarting Jellyfin..."
cd jellyfin
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# librespeed
echo "Restarting Librespeed..."
cd librespeed
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# # n8n
# echo "Restarting n8n..."
# cd n8n
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# # ollama
# echo "Restarting Ollama..."
# cd ollama
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# # open-webui
# echo "Restarting Open WebUI..."
# cd open-webui
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# pihole
echo "Restarting PiHole..."
cd pihole
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# # portainer
# echo "Restarting portainer..."
# cd portainer
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# scrutiny
echo "Restarting Scrutiny..."
cd scrutiny
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# silverbullet
echo "Restarting Silverbullet..."
cd silverbullet
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"

# # speaches
# echo "Restarting Speaches..."
# cd speaches
# # docker compose down
# time docker compose up -d
# cd ..
# echo -e "========================================\n\n"

# vikunja
echo "Restarting Vikunja..."
cd vikunja
# docker compose down
time docker compose up -d
cd ..
echo -e "========================================\n\n"
