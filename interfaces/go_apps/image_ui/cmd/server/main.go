package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/server"
)

func main() {
	addr := ":8091"
	if p := os.Getenv("IMAGE_UI_PORT"); p != "" {
		if p[0] == ':' {
			addr = p
		} else {
			addr = ":" + p
		}
	}

	srv := &http.Server{
		Addr:    addr,
		Handler: server.New().Routes(),
	}

	go func() {
		log.Printf("[image-ui] listening on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("shutdown error: %v", err)
	}
}
