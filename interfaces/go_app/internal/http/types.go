package httpserver

import (
	"errors"
	"sort"
	"strings"
	"time"
)

type Run struct {
	ID            string   `json:"id"`
	Mode          string   `json:"mode"`
	Status        string   `json:"status"`
	Headline      string   `json:"headline"`
	ResultSummary string   `json:"result_summary"`
	PlanSummary   string   `json:"plan_summary"`
	CreatedAt     string   `json:"created_at"`
	UpdatedAt     string   `json:"updated_at"`
	Tags          []string `json:"tags"`
	Machines      []string `json:"machines"`
	Commands      []string `json:"commands"`
	Tests         []string `json:"tests"`
	Artifacts     []string `json:"artifacts"`
	Notes         string   `json:"notes"`
}

func (r Run) DisplayTitle() string {
	if r.Headline != "" {
		return r.Headline
	}
	if r.ResultSummary != "" {
		text := strings.TrimSpace(r.ResultSummary)
		if len(text) > 80 {
			text = text[:77] + "…"
		}
		if text != "" {
			return text
		}
	}
	return strings.ToUpper(r.Mode) + " run"
}

func (r Run) UpdatedAtTime() (time.Time, error) {
	layouts := []string{
		"2006-01-02T15:04:05.000000Z",
		"2006-01-02T15:04:05.000Z",
		"2006-01-02T15:04:05Z",
	}
	for _, layout := range layouts {
		if t, err := time.Parse(layout, r.UpdatedAt); err == nil {
			return t, nil
		}
	}
	return time.Time{}, errors.New("unknown time format")
}

func (r Run) UpdatedLabel() string {
	t, err := r.UpdatedAtTime()
	if err != nil {
		return ""
	}
	return t.Local().Format("2006-01-02 15:04")
}

type Machine struct {
	Name      string  `json:"name"`
	Type      string  `json:"type"`
	Host      *string `json:"host"`
	Workspace string  `json:"workspace"`
	Notes     *string `json:"notes"`
}

type PolicyEntry struct {
	Key   string
	Value string
}

type Policy struct {
	Entries []PolicyEntry
}

func NewPolicy(effective map[string]string) Policy {
	entries := make([]PolicyEntry, 0, len(effective))
	for key, value := range effective {
		entries = append(entries, PolicyEntry{Key: key, Value: value})
	}
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Key < entries[j].Key
	})
	return Policy{Entries: entries}
}

type RunList struct {
	Items []Run
}

func (rl RunList) IDs() []string {
	ids := make([]string, 0, len(rl.Items))
	for _, run := range rl.Items {
		ids = append(ids, run.ID)
	}
	return ids
}
