FROM ghcr.io/astral-sh/uv:python3.11-alpine

# psutil needs to compile C code on Alpine, so we need gcc and headers
RUN apk add --no-cache gcc musl-dev linux-headers python3-dev

WORKDIR /app
COPY main.py .

CMD ["uv", "run", "main.py"]
