package main

import (
	"context"
	"net"
	"net/http"
	"testing"
	"time"
)

func TestNewHTTPServerConfiguresTimeouts(t *testing.T) {
	server := newHTTPServer("127.0.0.1:8082", http.NewServeMux())

	if server.ReadHeaderTimeout != serverReadHeaderTimeout {
		t.Fatalf("expected read header timeout %s, got %s", serverReadHeaderTimeout, server.ReadHeaderTimeout)
	}
	if server.ReadTimeout != serverReadTimeout {
		t.Fatalf("expected read timeout %s, got %s", serverReadTimeout, server.ReadTimeout)
	}
	if server.WriteTimeout != serverWriteTimeout {
		t.Fatalf("expected write timeout %s, got %s", serverWriteTimeout, server.WriteTimeout)
	}
	if server.IdleTimeout != serverIdleTimeout {
		t.Fatalf("expected idle timeout %s, got %s", serverIdleTimeout, server.IdleTimeout)
	}
}

func TestServeHTTPServerGracefullyShutsDownLongLivedConnections(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}

	shutdownCh := make(chan struct{})
	server := newHTTPServer(listener.Addr().String(), http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		if flusher, ok := w.(http.Flusher); ok {
			flusher.Flush()
		}

		select {
		case <-shutdownCh:
		case <-r.Context().Done():
		}
	}))
	server.RegisterOnShutdown(func() {
		close(shutdownCh)
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errCh := make(chan error, 1)
	go func() {
		errCh <- serveHTTPServer(ctx, server, listener)
	}()

	response, err := http.Get("http://" + listener.Addr().String())
	if err != nil {
		t.Fatalf("get response: %v", err)
	}
	defer response.Body.Close()

	cancel()

	select {
	case err := <-errCh:
		if err != nil {
			t.Fatalf("serveHTTPServer returned error: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for graceful shutdown")
	}
}
