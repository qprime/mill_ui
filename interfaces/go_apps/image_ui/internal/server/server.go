package server

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/config"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/gen"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/personas"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/root"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/store"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/styles"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/web"
)

var (
	personasRoot = filepath.Join(root.Dir(), "cortex", "personas", "cam", "artists")
	stylesRoot   = filepath.Join(root.Dir(), "cortex", "personas", "cam", "styles")
)

type Server struct {
	templates *template.Template
}

func New() *Server {
	funcMap := template.FuncMap{
		"toJSON": func(v any) string {
			b, err := json.Marshal(v)
			if err != nil {
				return "{}"
			}
			return string(b)
		},
	}
	t := template.Must(template.New("index.tmpl").Funcs(funcMap).ParseFS(web.TemplatesFS, "templates/index.tmpl"))
	return &Server{templates: t}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()

	mux.Handle("/image-ui/static/", http.StripPrefix("/image-ui/static/", http.FileServer(http.FS(web.StaticFS))))
	mux.HandleFunc("/image-ui/api/personas", s.handlePersonas)
	mux.HandleFunc("/image-ui/api/styles", s.handleStyles)
	mux.HandleFunc("/image-ui/api/projects", s.handleProjects)
	mux.HandleFunc("/image-ui/api/projects/", s.handleProjectInput)
	mux.HandleFunc("/image-ui/api/generate", s.handleGenerate)
	mux.HandleFunc("/image-ui/api/gallery/", s.handleGallery)
	mux.HandleFunc("/image-ui/files/", s.handleFile)
	mux.HandleFunc("/image-ui/", s.handleIndex)
	mux.HandleFunc("/", redirect("/image-ui/"))

	return loggingMiddleware(mux)
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/image-ui/" {
		http.NotFound(w, r)
		return
	}
	if err := store.EnsureProjectsRoot(); err != nil {
		http.Error(w, fmt.Sprintf("failed to prepare projects: %v", err), http.StatusInternalServerError)
		return
	}
	projects, err := store.ListProjects()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	cssBytes, err := web.StaticFS.ReadFile("static/style.css")
	if err != nil {
		log.Printf("[warn] failed to load style.css: %v", err)
	}
	data := map[string]any{
		"Projects":   projects,
		"KeyPresent": config.APIKey() != "",
		"StyleCSS":   template.CSS(string(cssBytes)),
	}
	if err := s.templates.ExecuteTemplate(w, "index.tmpl", data); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func (s *Server) handlePersonas(w http.ResponseWriter, r *http.Request) {
	plist, err := personas.Load(personasRoot)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, plist)
}

func (s *Server) handleStyles(w http.ResponseWriter, r *http.Request) {
	slist, err := styles.Load(stylesRoot)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, slist)
}

func (s *Server) handleProjects(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		projects, err := store.ListProjects()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, projects)
	case http.MethodPost:
		var body struct {
			Name string `json:"name"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}
		if strings.TrimSpace(body.Name) == "" {
			http.Error(w, "name required", http.StatusBadRequest)
			return
		}
		project, err := store.CreateProject(body.Name)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, map[string]any{"ok": true, "name": project})
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func (s *Server) handleProjectInput(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/image-ui/api/projects/")
	parts := strings.SplitN(path, "/", 2)
	if len(parts) != 2 || parts[1] != "input" {
		http.NotFound(w, r)
		return
	}
	project := parts[0]
	switch r.Method {
	case http.MethodGet:
		cfg, err := store.LoadInput(project)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, cfg)
	case http.MethodPost:
		var cfg store.InputConfig
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}
		if cfg.Size == "" {
			cfg.Size = "1024x1024"
		}
		if err := store.SaveInput(project, &cfg); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, map[string]any{"ok": true})
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func (s *Server) handleGenerate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	if config.APIKey() == "" {
		http.Error(w, "OpenAI API key not configured. Export OPENAI_API_KEY and restart.", http.StatusUnauthorized)
		return
	}
	var body struct {
		Project string `json:"project"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(body.Project) == "" {
		http.Error(w, "project required", http.StatusBadRequest)
		return
	}
	output, err := gen.Run(body.Project)
	if err != nil {
		log.Printf("[generate] error: %v\n%s", err, output)
		http.Error(w, fmt.Sprintf("Image service unavailable: %s", output), http.StatusBadGateway)
		return
	}
	log.Printf("[generate] success %s", body.Project)
	writeJSON(w, map[string]any{"ok": true})
}

func (s *Server) handleGallery(w http.ResponseWriter, r *http.Request) {
	project := strings.TrimPrefix(r.URL.Path, "/image-ui/api/gallery/")
	if project == "" {
		http.NotFound(w, r)
		return
	}
	items, err := store.ListImages(project)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{"images": items})
}

func (s *Server) handleFile(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/image-ui/files/")
	parts := strings.SplitN(rest, "/", 2)
	if len(parts) != 2 {
		http.NotFound(w, r)
		return
	}
	project := parts[0]
	name := parts[1]
	if strings.Contains(project, "..") || strings.Contains(name, "..") {
		http.NotFound(w, r)
		return
	}
	path, err := store.ImagePath(project, filepath.Base(name))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	http.ServeFile(w, r, path)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
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
		sw := &statusWriter{ResponseWriter: w}
		next.ServeHTTP(sw, r)
		log.Printf("%s %s -> %d (%dB)", r.Method, r.URL.Path, sw.status, sw.bytes)
	})
}
