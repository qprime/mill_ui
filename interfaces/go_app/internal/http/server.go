package httpserver

import (
	"context"
	"log"
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
	mux.HandleFunc("/ace/sse/", s.handleSSE)
	mux.HandleFunc("/ace/hx/new", s.handleNewChatForm)
	mux.HandleFunc("/ace", s.handleAce)
	mux.HandleFunc("/", redirect("/ace"))
	return loggingMiddleware(mux)
}

func (s *Server) withTimeout(r *http.Request) (context.Context, context.CancelFunc) {
	ctx := r.Context()
	deadline := 30 * time.Second
	if r.Method == http.MethodPost {
		deadline = 45 * time.Second
	}
	return context.WithTimeout(ctx, deadline)
}

func redirect(path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, path, http.StatusFound)
	}
}

type statusWriter struct {
	http.ResponseWriter
	status int
	bytes  int
}

func (sw *statusWriter) WriteHeader(code int) {
	sw.status = code
	sw.ResponseWriter.WriteHeader(code)
}

func (sw *statusWriter) Write(b []byte) (int, error) {
	if sw.status == 0 {
		sw.status = http.StatusOK
	}
	n, err := sw.ResponseWriter.Write(b)
	sw.bytes += n
	return n, err
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w}
		next.ServeHTTP(sw, r)
		dur := time.Since(start)
		log.Printf("%s %s -> %d (%dB) %s", r.Method, r.URL.Path, sw.status, sw.bytes, dur)
	})
}
