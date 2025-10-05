package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/root"
)

type InputConfig struct {
	Subject  string         `json:"subject"`
	Persona  string         `json:"persona"`
	Style    string         `json:"style"`
	Size     string         `json:"size"`
	Prompt   string         `json:"prompt,omitempty"`
	Image    string         `json:"image,omitempty"`
	Metadata map[string]any `json:"metadata,omitempty"`
}

type ImageInfo struct {
	Name     string `json:"name"`
	Latest   bool   `json:"latest"`
	Modified int64  `json:"modified"`
}

func projectsRoot() (string, error) {
	return filepath.Join(root.Dir(), "memories", "cam_projects"), nil
}

func projectInputDir(project string) (string, error) {
	rootDir, err := projectsRoot()
	if err != nil {
		return "", err
	}
	return filepath.Join(rootDir, project, "input"), nil
}

func ListProjects() ([]string, error) {
	root, err := projectsRoot()
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []string{}, nil
		}
		return nil, err
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() {
			names = append(names, entry.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}

func SanitizeProject(name string) string {
	var b strings.Builder
	for _, r := range name {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			b.WriteRune(r)
		}
	}
	if b.Len() == 0 {
		return "project"
	}
	return b.String()
}

func CreateProject(name string) (string, error) {
	project := SanitizeProject(name)
	dir, err := projectInputDir(project)
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	cfgPath := filepath.Join(dir, "image.json")
	if _, err := os.Stat(cfgPath); errors.Is(err, os.ErrNotExist) {
		cfg := InputConfig{Size: "1024x1024"}
		if err := writeJSON(cfgPath, &cfg); err != nil {
			return "", err
		}
	}
	return project, nil
}

func LoadInput(project string) (*InputConfig, error) {
	dir, err := projectInputDir(project)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	cfgPath := filepath.Join(dir, "image.json")
	cfg := &InputConfig{Size: "1024x1024"}
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			if err := writeJSON(cfgPath, cfg); err != nil {
				return nil, err
			}
			return cfg, nil
		}
		return nil, err
	}
	if err := json.Unmarshal(data, cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func SaveInput(project string, cfg *InputConfig) error {
	dir, err := projectInputDir(project)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	return writeJSON(filepath.Join(dir, "image.json"), cfg)
}

func writeJSON(path string, cfg *InputConfig) error {
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func ListImages(project string) ([]ImageInfo, error) {
	dir, err := projectInputDir(project)
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []ImageInfo{}, nil
		}
		return nil, err
	}
	infos := make([]ImageInfo, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !(name == "image.png" || (strings.HasPrefix(name, "image-") && strings.HasSuffix(name, ".png"))) {
			continue
		}
		stat, err := entry.Info()
		if err != nil {
			continue
		}
		infos = append(infos, ImageInfo{
			Name:     name,
			Latest:   name == "image.png",
			Modified: stat.ModTime().Unix(),
		})
	}
	sort.Slice(infos, func(i, j int) bool {
		return infos[i].Modified > infos[j].Modified
	})
	return infos, nil
}

func ImagePath(project, name string) (string, error) {
	if strings.Contains(name, "..") {
		return "", fmt.Errorf("invalid image name")
	}
	dir, err := projectInputDir(project)
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, name), nil
}

func EnsureProjectsRoot() error {
	root, err := projectsRoot()
	if err != nil {
		return err
	}
	return os.MkdirAll(root, 0o755)
}
