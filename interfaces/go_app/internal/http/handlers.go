package httpserver

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"strings"

	"github.com/squinlan/cliff_ai/interfaces/go_app/internal/views"
)

func (s *Server) handleAce(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		runs = nil
	}
	machines, errMachines := s.client.ListMachines(ctx)
	if errMachines != nil {
		machines = nil
	}
	policy, errPolicy := s.client.FetchPolicy(ctx)

	viewRuns := convertRuns(runs)
	var current *views.Run
	if len(viewRuns) > 0 {
		current = &viewRuns[0]
	}

	page := views.PageData{
		Title:      "ACE Console",
		Runs:       viewRuns,
		CurrentRun: current,
		Machines:   convertMachines(machines),
		Policy:     convertPolicy(policy),
	}
	if err != nil {
		page.ErrorMessage = "Unable to load run history"
	} else if errMachines != nil {
		page.ErrorMessage = "Unable to load machine list"
	} else if errPolicy != nil {
		page.ErrorMessage = "Unable to load operate policy"
	}

	_ = views.Render(w, views.Page(page))
}

func (s *Server) handleRunList(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		http.Error(w, "Failed to load runs", http.StatusBadGateway)
		return
	}
	current := r.URL.Query().Get("current")
	_ = views.Render(w, views.RunListPartial(convertRuns(runs), current))
}

func (s *Server) handleRunDetail(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/ace/hx/runs/")
	if id == "" {
		http.Error(w, "missing run id", http.StatusBadRequest)
		return
	}
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	run, err := s.client.GetRun(ctx, id)
	if err != nil {
		http.Error(w, "Failed to load run", http.StatusBadGateway)
		return
	}
	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		// fallback to the single run
		runs = []Run{*run}
	}
	_ = views.Render(w, views.RunDetailPartial(convertRunPtr(run), convertRuns(runs)))
}

func (s *Server) handleMachineList(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	machines, err := s.client.ListMachines(ctx)
	if err != nil {
		http.Error(w, "Failed to load machines", http.StatusBadGateway)
		return
	}
	_ = views.Render(w, views.MachineListPartial(convertMachines(machines)))
}

func (s *Server) handlePolicy(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	policy, err := s.client.FetchPolicy(ctx)
	if err != nil {
		http.Error(w, "Failed to load policy", http.StatusBadGateway)
		return
	}
	_ = views.Render(w, views.PolicyPartial(convertPolicy(policy)))
}

func (s *Server) handleChat(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}
	text := strings.TrimSpace(r.FormValue("text"))
	if text == "" {
		http.Error(w, "Provide a prompt", http.StatusBadRequest)
		return
	}

	ctx, cancel := s.withTimeout(r)
	defer cancel()

	run, err := s.client.CreateChatRun(ctx, text)
	if err != nil {
		http.Error(w, errMessage(err), http.StatusBadGateway)
		return
	}

	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		runs = []Run{*run}
	}
	w.Header().Set("HX-Trigger", "runs-refresh")
	_ = views.Render(w, views.RunDetailPartial(convertRunPtr(run), convertRuns(runs)))
}

func convertRuns(runs []Run) []views.Run {
	result := make([]views.Run, 0, len(runs))
	for _, run := range runs {
		result = append(result, convertRunValue(run))
	}
	return result
}

func convertRunPtr(run *Run) *views.Run {
	if run == nil {
		return nil
	}
	v := convertRunValue(*run)
	return &v
}

func convertRunValue(run Run) views.Run {
	return views.Run{
		ID:            run.ID,
		Mode:          run.Mode,
		Status:        strings.ToLower(run.Status),
		Title:         run.DisplayTitle(),
		UpdatedLabel:  run.UpdatedLabel(),
		ResultSummary: run.ResultSummary,
		PlanSummary:   run.PlanSummary,
		Commands:      append([]string(nil), run.Commands...),
		Tests:         append([]string(nil), run.Tests...),
		Artifacts:     append([]string(nil), run.Artifacts...),
		Notes:         run.Notes,
		Tags:          append([]string(nil), run.Tags...),
	}
}

func convertMachines(machines []Machine) []views.Machine {
	result := make([]views.Machine, 0, len(machines))
	for _, machine := range machines {
		host := ""
		if machine.Host != nil {
			host = *machine.Host
		}
		notes := ""
		if machine.Notes != nil {
			notes = *machine.Notes
		}
		result = append(result, views.Machine{
			Name:      machine.Name,
			Type:      machine.Type,
			Host:      host,
			Workspace: machine.Workspace,
			Notes:     notes,
		})
	}
	return result
}

func convertPolicy(policy Policy) []views.PolicyEntry {
	entries := make([]views.PolicyEntry, 0, len(policy.Entries))
	for _, entry := range policy.Entries {
		entries = append(entries, views.PolicyEntry{Key: entry.Key, Value: entry.Value})
	}
	return entries
}

func errMessage(err error) string {
	var e *url.Error
	if errors.As(err, &e) {
		return "backend unavailable"
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return "request timed out"
	}
	return err.Error()
}
