#!/bin/bash
docker run --rm --env-file .env -v "$(pwd):/app" -w /app ghcr.io/opentofu/opentofu "$@"
