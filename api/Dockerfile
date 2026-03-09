# build go binary
FROM golang:alpine AS builder

RUN apk add --no-cache \
    gcc \
    musl-dev \
    sqlite-dev

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=1 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o api .

# copy over the binary and run
FROM alpine

RUN apk add --no-cache ca-certificates

WORKDIR /app

COPY --from=builder /app/api /app/api

ENV KILTER_TOGETHER_DATA_DIR=/data

EXPOSE 8082
VOLUME ["/data"]

ENTRYPOINT ["./api"]
CMD ["serve"]
