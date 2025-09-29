package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	httpserver "github.com/squinlan/cliff_ai/interfaces/go_app/internal/http"
)

func main() {
	backendURL := os.Getenv("ACE_BACKEND_URL")
	if backendURL == "" {
		backendURL = "https://127.0.0.1:8080/ace"
	}

	client := httpserver.NewClient(backendURL, backendTimeout())
	server := httpserver.NewServer(client)

	h := server.Routes()

	httpServer := &http.Server{
		Addr:    addr(),
		Handler: h,
	}

	go func() {
		certFile, keyFile := certPaths()
		log.Printf("[go-ace] listening (HTTPS) on %s", httpServer.Addr)
		if err := httpServer.ListenAndServeTLS(certFile, keyFile); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen (tls): %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("shutdown error: %v", err)
	}
}

func addr() string {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8090"
	}
	if port[0] != ':' {
		return ":" + port
	}
	return port
}

func backendTimeout() time.Duration {
	if raw := os.Getenv("ACE_BACKEND_TIMEOUT"); raw != "" {
		if d, err := time.ParseDuration(raw); err == nil {
			if d > 0 {
				return d
			}
		}
	}
	return 60 * time.Second
}

// certPaths resolves TLS certificate and key locations.
// Order of precedence:
//  1. ACE_TLS_CERT and ACE_TLS_KEY env vars
//  2. interfaces/cert/web_server.{crt,key} relative to cwd
//  3. ../cert/web_server.{crt,key} relative to cwd (common when running from interfaces/go_app)
func certPaths() (string, string) {
	cert := os.Getenv("ACE_TLS_CERT")
	key := os.Getenv("ACE_TLS_KEY")
	if cert != "" && key != "" {
		return cert, key
	}
	candidates := [][2]string{
		{"interfaces/cert/web_server.crt", "interfaces/cert/web_server.key"},
		{filepath.Clean("../cert/web_server.crt"), filepath.Clean("../cert/web_server.key")},
	}
	for _, pair := range candidates {
		if fileExists(pair[0]) && fileExists(pair[1]) {
			return pair[0], pair[1]
		}
	}
	// Fallback: instruct user via log and use placeholders (this will fail fast)
	log.Printf("TLS certs not found; set ACE_TLS_CERT and ACE_TLS_KEY or run from repo root")
	return "interfaces/cert/web_server.crt", "interfaces/cert/web_server.key"
}

func fileExists(p string) bool {
	if p == "" {
		return false
	}
	if st, err := os.Stat(p); err == nil && !st.IsDir() {
		return true
	}
	return false
}
