package gen

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/root"
)

// Run invokes the Python generator with versioning for a given project.
func Run(project string) (string, error) {
	python := os.Getenv("PYTHON_BIN")
	if python == "" {
		python = "python"
	}
	cmd := exec.Command(python, "-m", "skills.image_pipeline.generate_versioned_image", project)
	cmd.Dir = root.Dir()
	cmd.Env = os.Environ()
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		out := stdout.String() + stderr.String()
		if out == "" {
			out = err.Error()
		}
		return out, fmt.Errorf("generation failed: %w", err)
	}
	return stdout.String(), nil
}

func EnsurePython() (string, error) {
	python := os.Getenv("PYTHON_BIN")
	if python == "" {
		python = "python"
	}
	path, err := exec.LookPath(python)
	if err != nil {
		return "", fmt.Errorf("python executable not found: %v", err)
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		return path, nil
	}
	return abs, nil
}
