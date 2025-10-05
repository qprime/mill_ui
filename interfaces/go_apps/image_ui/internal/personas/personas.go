package personas

import (
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
)

type Persona struct {
	Name            string   `json:"name"`
	Genre           string   `json:"genre"`
	PromptingStyle  string   `json:"prompting_style"`
	PreferredStyles []string `json:"preferred_styles"`
}

// Load returns a map of persona name to persona metadata.
func Load(root string) (map[string]Persona, error) {
	result := make(map[string]Persona)
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		if filepath.Ext(entry.Name()) != ".json" {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var p Persona
		if err := json.Unmarshal(data, &p); err != nil {
			return nil
		}
		if p.Name != "" {
			result[p.Name] = p
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return result, nil
}
