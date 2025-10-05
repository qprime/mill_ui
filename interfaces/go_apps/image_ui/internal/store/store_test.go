package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestCreateLoadSaveProject(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("wd: %v", err)
	}
	tmp := t.TempDir()
	if err := os.Chdir(tmp); err != nil {
		t.Fatalf("chdir: %v", err)
	}
	t.Cleanup(func() { _ = os.Chdir(wd) })

	project, err := CreateProject("Example Project!")
	if err != nil {
		t.Fatalf("CreateProject: %v", err)
	}
	if project == "" {
		t.Fatalf("expected sanitized project name")
	}

	cfg, err := LoadInput(project)
	if err != nil {
		t.Fatalf("LoadInput: %v", err)
	}
	cfg.Subject = "rose"
	cfg.Persona = "mira"
	cfg.Style = "flat_plane"
	if err := SaveInput(project, cfg); err != nil {
		t.Fatalf("SaveInput: %v", err)
	}

	cfg2, err := LoadInput(project)
	if err != nil {
		t.Fatalf("LoadInput 2: %v", err)
	}
	if cfg2.Subject != "rose" || cfg2.Persona != "mira" || cfg2.Style != "flat_plane" {
		t.Fatalf("unexpected config: %+v", cfg2)
	}

	dir, err := projectInputDir(project)
	if err != nil {
		t.Fatalf("projectInputDir: %v", err)
	}
	imagePath := filepath.Join(dir, "image.png")
	if err := os.WriteFile(imagePath, []byte("png"), 0o644); err != nil {
		t.Fatalf("write image: %v", err)
	}
	infos, err := ListImages(project)
	if err != nil {
		t.Fatalf("ListImages: %v", err)
	}
	if len(infos) != 1 || infos[0].Name != "image.png" {
		t.Fatalf("unexpected infos: %+v", infos)
	}
}

func TestWriteJSON(t *testing.T) {
	wd, _ := os.Getwd()
	tmp := t.TempDir()
	_ = os.Chdir(tmp)
	t.Cleanup(func() { _ = os.Chdir(wd) })

	cfg := &InputConfig{Subject: "test"}
	if err := writeJSON("test.json", cfg); err != nil {
		t.Fatalf("writeJSON: %v", err)
	}
	data, err := os.ReadFile("test.json")
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	var decoded InputConfig
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if decoded.Subject != "test" {
		t.Fatalf("unexpected subject: %q", decoded.Subject)
	}
}
