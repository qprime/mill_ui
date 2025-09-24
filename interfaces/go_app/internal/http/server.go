package httpserver

import (
	"context"
	"net/http"
	"time"
)

type Server struct {
	client *Client
}

func NewServer(client *Client) *Server {
	return &Server{client: client}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/static/", staticHandler())
	mux.HandleFunc("/ace/hx/runs", s.handleRunList)
	mux.HandleFunc("/ace/hx/runs/", s.handleRunDetail)
	mux.HandleFunc("/ace/hx/machines", s.handleMachineList)
	mux.HandleFunc("/ace/hx/policy", s.handlePolicy)
	mux.HandleFunc("/ace/hx/chat", s.handleChat)
	mux.HandleFunc("/ace", s.handleAce)
	mux.HandleFunc("/", redirect("/ace"))
	return loggingMiddleware(mux)
}

func (s *Server) withTimeout(r *http.Request) (context.Context, context.CancelFunc) {
	ctx := r.Context()
	return context.WithTimeout(ctx, 10*time.Second)
}

func redirect(path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, path, http.StatusFound)
	}
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		_ = start
	})
}
