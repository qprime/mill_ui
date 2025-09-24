package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	httpserver "github.com/squinlan/cliff_ai/interfaces/go_app/internal/http"
)

func main() {
	backendURL := os.Getenv("ACE_BACKEND_URL")
	if backendURL == "" {
		backendURL = "http://127.0.0.1:8080/ace"
	}

	client := httpserver.NewClient(backendURL, 15*time.Second)
	server := httpserver.NewServer(client)

	h := server.Routes()

	httpServer := &http.Server{
		Addr:    addr(),
		Handler: h,
	}

	go func() {
		log.Printf("[go-ace] listening on %s", httpServer.Addr)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
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
