FROM rust:alpine AS builder
WORKDIR /app
RUN apk add --no-cache musl-dev perl make
COPY . .
RUN cargo build --release

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/target/release/ollama-rss-rust .
EXPOSE 5500
CMD ["./ollama-rss-rust"]
