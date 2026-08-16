FROM --platform=$BUILDPLATFORM golang:1.25.10-alpine AS builder

ARG TARGETOS
ARG TARGETARCH
ARG ENGRAM_REPO_URL=https://github.com/Gentleman-Programming/engram.git
ARG ENGRAM_REF=1dafc0f63051b2214100f7bd801357e4aab61c26
ARG ENGRAM_VERSION=1.20.1-0.20260814074340-1dafc0f63051+addon

RUN apk add --no-cache git
WORKDIR /src
RUN git clone --filter=blob:none "$ENGRAM_REPO_URL" . \
    && git fetch --depth=1 origin "$ENGRAM_REF" \
    && git checkout --detach "$ENGRAM_REF" \
    && test "$(git rev-parse HEAD)" = "$ENGRAM_REF"

COPY patches/engram-source-agent.patch /tmp/engram-source-agent.patch
RUN git apply --check /tmp/engram-source-agent.patch \
    && git apply /tmp/engram-source-agent.patch
RUN go mod download
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH:-amd64} \
    go build -trimpath -ldflags="-X main.version=${ENGRAM_VERSION}" -o /out/engram ./cmd/engram

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata \
    && adduser -D -u 10001 engram
USER engram
WORKDIR /home/engram
COPY --from=builder /out/engram /usr/local/bin/engram

EXPOSE 18080
ENTRYPOINT ["engram"]
CMD ["cloud", "serve"]
