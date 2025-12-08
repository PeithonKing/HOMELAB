# pihole
echo "Restarting PiHole..."
cd pihole
# docker compose down
time docker compose up -d
cd ..
echo ========================================\n\n

# glance
echo "Restarting Glance..."
cd glance
# docker compose down
time docker compose up -d
cd ..
echo ========================================\n\n

# # immich
# echo "Restarting Immich..."
# cd immich
# # docker compose down
# time docker compose up -d
# cd ..
# echo ========================================\n\n

# jellyfin
echo "Restarting Jellyfin..."
cd jellyfin
# docker compose down
time docker compose up -d
cd ..
echo ========================================\n\n

# # n8n
# echo "Restarting n8n..."
# cd n8n
# # docker compose down
# time docker compose up -d
# cd ..
# echo ========================================\n\n

# open-webui
echo "Restarting Open WebUI..."
cd open-webui
# docker compose down
time docker compose up -d
cd ..
echo ========================================\n\n

# # speaches
# echo "Restarting Speaches..."
# cd speaches
# # docker compose down
# time docker compose up -d
# cd ..
# echo ========================================\n\n

# portainer
echo "Restarting portainer..."
cd portainer
# docker compose down
time docker compose up -d
cd ..
echo ========================================\n\n
