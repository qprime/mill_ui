package styles

import (
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
)

type Style struct {
	Name                string `json:"name"`
	MachinabilityPrompt string `json:"machinability_prompt"`
}

func Load(root string) (map[string]Style, error) {
	styles := make(map[string]Style)
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
		var s Style
		if err := json.Unmarshal(data, &s); err != nil {
			return nil
		}
		if s.Name != "" {
			styles[s.Name] = s
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return styles, nil
}
