package root

import (
	"os"
	"path/filepath"
	"runtime"
	"sync"
)

var (
	repoDir string
	once    sync.Once
)

// Dir returns the absolute path to the repository root.
func Dir() string {
	once.Do(func() {
		if wd, err := os.Getwd(); err == nil {
			repoDir = wd
		}
		if _, file, _, ok := runtime.Caller(0); ok {
			dir := filepath.Dir(file) // .../interfaces/go_apps/image_ui/internal/root
			repoDir = filepath.Clean(filepath.Join(dir, "..", "..", "..", "..", ".."))
		}
	})
	return repoDir
}
