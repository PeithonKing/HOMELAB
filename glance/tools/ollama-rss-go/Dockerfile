FROM golang:alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o ollama-rss main.go

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/ollama-rss .
EXPOSE 5500
CMD ["./ollama-rss"]
