package httpserver

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/squinlan/cliff_ai/interfaces/go_app/internal/views"
)

func (s *Server) handleAce(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()

	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		runs = nil
	}
	allRuns := append([]Run(nil), runs...)
	runs = filterChatRuns(runs)
	sort.Slice(runs, func(i, j int) bool { // newest first
		return parseRunTime(runs[i].UpdatedAt).After(parseRunTime(runs[j].UpdatedAt))
	})
	runs = collapseThreads(runs)
	machines, errMachines := s.client.ListMachines(ctx)
	if errMachines != nil {
		machines = nil
	}
	policy, errPolicy := s.client.FetchPolicy(ctx)

	viewRuns := convertRuns(runs)
	var current *views.Run
	if len(viewRuns) > 0 {
		hydrated := viewRuns[0]
		if orig := runByID(allRuns, hydrated.ID); orig != nil {
			hydrated.Conversation = s.conversationForRun(ctx, orig.ID, orig.Tags, allRuns)
		} else {
			hydrated.Conversation = s.conversationForRun(ctx, hydrated.ID, nil, allRuns)
		}
		current = &hydrated
	}

	selModel, modelOptions := s.modelOptions(ctx)
	thread := extractThread(current)
	if thread == "" {
		thread = genID()
	}
	continueID := ""
	if current != nil {
		continueID = current.ID
	}

	page := views.PageData{
		Title:         "ACE Chat",
		Runs:          viewRuns,
		CurrentRun:    current,
		Machines:      convertMachines(machines),
		Policy:        convertPolicy(policy),
		SelectedModel: selModel,
		ModelOptions:  modelOptions,
		Thread:        thread,
		ContinueRunID: continueID,
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
	runs = filterChatRuns(runs)
	sort.Slice(runs, func(i, j int) bool { // newest first
		return parseRunTime(runs[i].UpdatedAt).After(parseRunTime(runs[j].UpdatedAt))
	})
	runs = collapseThreads(runs)
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
	allRuns := append([]Run(nil), runs...)
	runs = filterChatRuns(runs)
	sort.Slice(runs, func(i, j int) bool { // newest first
		return parseRunTime(runs[i].UpdatedAt).After(parseRunTime(runs[j].UpdatedAt))
	})
	runs = collapseThreads(runs)
	vr := convertRunPtr(run)
	if vr != nil {
		vr.Conversation = s.conversationForRun(ctx, run.ID, run.Tags, allRuns)
	}
	_ = views.Render(w, views.RunDetailPartial(vr, convertRuns(runs)))
	// Out-of-band update for chat form to continue this run
	selModel, modelOptions := s.modelOptions(ctx)
	thread := extractThread(vr)
	if thread == "" {
		thread = genID()
	}
	_ = views.Render(w, views.ChatFormOOB(thread, selModel, modelOptions, vr.ID))
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
	model := strings.TrimSpace(r.FormValue("model"))
	thread := strings.TrimSpace(r.FormValue("thread"))
	continueID := strings.TrimSpace(r.FormValue("continue"))

	ctx, cancel := s.withTimeout(r)
	defer cancel()

	existingRuns, err := s.client.ListRuns(ctx)
	if err != nil {
		existingRuns = nil
	}

	if thread == "" && continueID != "" {
		if r := runByID(existingRuns, continueID); r != nil {
			thread = threadFromTags(r.Tags)
		}
	}

	baseConv := []ChatMessage{}
	if thread != "" {
		if latest := latestRunInThread(thread, existingRuns); latest != nil {
			if msgs, err := s.client.GetConversation(ctx, latest.ID); err == nil {
				baseConv = msgs
			}
		}
	} else if continueID != "" {
		if msgs, err := s.client.GetConversation(ctx, continueID); err == nil {
			baseConv = msgs
		}
	}

	tags := []string{"chat"}
	if thread != "" {
		tags = append(tags, "thread:"+thread)
	}

	run, err := s.client.CreateChatRunWith(ctx, text, baseConv, tags, model)
	if err != nil {
		log.Printf("create chat error: %v", err)
		if errors.Is(err, ErrPlanRequired) {
			w.WriteHeader(http.StatusAccepted)
			_ = views.Render(w, views.PlanRequired(errMessage(err)))
			return
		}
		http.Error(w, errMessage(err), http.StatusBadGateway)
		return
	}

	runs, err := s.client.ListRuns(ctx)
	if err != nil {
		runs = []Run{*run}
	}
	allRuns := append([]Run(nil), runs...)
	runs = filterChatRuns(runs)
	runs = collapseThreads(runs)
	w.Header().Set("HX-Trigger", "runs-refresh")
	vr := convertRunPtr(run)
	if vr != nil {
		vr.Conversation = s.conversationForRun(ctx, run.ID, run.Tags, allRuns)
	}
	_ = views.Render(w, views.RunDetailPartial(vr, convertRuns(runs)))
	// OOB: update chat form to continue this new run under same thread
	selModel, modelOptions := s.modelOptions(ctx)
	thr := thread
	if thr == "" {
		thr = threadFromTags(run.Tags)
	}
	if thr == "" {
		thr = extractThread(vr)
	}
	if thr == "" {
		thr = genID()
	}
	_ = views.Render(w, views.ChatFormOOB(thr, selModel, modelOptions, vr.ID))
}

// Proxy SSE stream from backend so browser can connect to same origin.
func (s *Server) handleSSE(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/ace/sse/")
	if id == "" {
		http.Error(w, "missing run id", http.StatusBadRequest)
		return
	}
	ctx := r.Context() // no fixed deadline; client controls lifecycle
	body, res, err := s.client.StreamSSE(ctx, fmt.Sprintf("/runs/%s/sse", url.PathEscape(id)))
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer body.Close()

	// Mirror important headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	if v := res.Header.Get("X-Accel-Buffering"); v != "" {
		w.Header().Set("X-Accel-Buffering", v)
	} else {
		w.Header().Set("X-Accel-Buffering", "no")
	}

	flusher, _ := w.(http.Flusher)
	buf := make([]byte, 4096)
	for {
		n, readErr := body.Read(buf)
		if n > 0 {
			if _, writeErr := w.Write(buf[:n]); writeErr != nil {
				break
			}
			if flusher != nil {
				flusher.Flush()
			}
		}
		if readErr != nil {
			break
		}
	}
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

func (s *Server) fetchConversation(ctx context.Context, runID string) []views.ChatMessage {
	msgs, err := s.client.GetConversation(ctx, runID)
	if err != nil || len(msgs) == 0 {
		return nil
	}
	out := make([]views.ChatMessage, 0, len(msgs))
	for _, m := range msgs {
		out = append(out, views.ChatMessage{Role: m.Role, Content: m.Content})
	}
	return out
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
	if errors.Is(err, ErrPlanRequired) {
		return "plan preview required before execution"
	}
	return err.Error()
}

// Helpers -------------------------------------------------------------
func filterChatRuns(runs []Run) []Run {
	out := make([]Run, 0, len(runs))
	for _, r := range runs {
		if strings.EqualFold(strings.TrimSpace(r.Mode), "ideate") || strings.EqualFold(strings.TrimSpace(r.Mode), "chat") {
			out = append(out, r)
		}
	}
	return out
}

func collapseThreads(runs []Run) []Run {
	seen := make(map[string]struct{}, len(runs))
	result := make([]Run, 0, len(runs))
	for _, r := range runs {
		key := threadFromTags(r.Tags)
		if key == "" {
			key = r.ID
		}
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		result = append(result, r)
	}
	return result
}

func (s *Server) modelOptions(ctx context.Context) (string, []views.ModelOption) {
	cfg, err := s.client.FetchRouterConfig(ctx)
	if err != nil {
		return "gpt-5", []views.ModelOption{{Value: "gpt-5", Label: "gpt-5", Group: "OpenAI API"}}
	}
	providers := cfg.Providers
	providerNames := make([]string, 0, len(providers))
	for name := range providers {
		providerNames = append(providerNames, name)
	}
	sort.Strings(providerNames)
	groupOrder := map[string]int{
		"OpenAI API": 0,
		"Codex CLI":  1,
		"Other":      2,
	}
	opts := make([]views.ModelOption, 0, len(providerNames))
	for _, name := range providerNames {
		prov := providers[name]
		group := "Other"
		switch {
		case strings.HasPrefix(name, "gpt_api"):
			group = "OpenAI API"
		case strings.Contains(name, "codex"):
			group = "Codex CLI"
		}
		value := prov.Model
		if value == "" {
			value = name
		}
		label := value
		if prov.Model != "" {
			label = prov.Model
		}
		if group == "Codex CLI" && prov.Model == "" {
			label = strings.ReplaceAll(name, "_", " ") + " (router default)"
		}
		opts = append(opts, views.ModelOption{
			Value:    value,
			Label:    label,
			Group:    group,
			Disabled: group == "Codex CLI" && prov.Model == "",
		})
	}
	sort.SliceStable(opts, func(i, j int) bool {
		ig := groupOrder[opts[i].Group]
		jg := groupOrder[opts[j].Group]
		if ig != jg {
			return ig < jg
		}
		return opts[i].Label < opts[j].Label
	})
	sel := "gpt-5"
	if tt, ok := cfg.TaskTypes["chat"]; ok {
		if prov, ok2 := providers[tt.Provider]; ok2 {
			if prov.Model != "" {
				sel = prov.Model
			} else {
				sel = tt.Provider
			}
		}
	}
	if disableSelected(sel, opts) {
		for _, opt := range opts {
			if !opt.Disabled {
				sel = opt.Value
				break
			}
		}
	}
	if len(opts) == 0 {
		opts = []views.ModelOption{{Value: sel, Label: sel, Group: "OpenAI API"}}
	}
	return sel, opts
}

func extractThread(run *views.Run) string {
	if run == nil {
		return ""
	}
	for _, t := range run.Tags {
		if strings.HasPrefix(t, "thread:") {
			return strings.TrimPrefix(t, "thread:")
		}
	}
	return ""
}

func threadFromTags(tags []string) string {
	for _, t := range tags {
		if strings.HasPrefix(t, "thread:") {
			return strings.TrimPrefix(t, "thread:")
		}
	}
	return ""
}

// latestRunInThread finds the run with the most recent UpdatedAt for a thread id.
func latestRunInThread(thread string, runs []Run) *Run {
	var best *Run
	for i := range runs {
		if threadFromTags(runs[i].Tags) != thread {
			continue
		}
		if best == nil || parseRunTime(runs[i].UpdatedAt).After(parseRunTime(best.UpdatedAt)) {
			r := runs[i]
			best = &r
		}
	}
	return best
}

func disableSelected(value string, opts []views.ModelOption) bool {
	if value == "" {
		return false
	}
	for _, opt := range opts {
		if opt.Value == value {
			return opt.Disabled
		}
	}
	return false
}

func runByID(runs []Run, id string) *Run {
	for i := range runs {
		if runs[i].ID == id {
			return &runs[i]
		}
	}
	return nil
}

func (s *Server) conversationForRun(ctx context.Context, runID string, tags []string, allRuns []Run) []views.ChatMessage {
	thread := threadFromTags(tags)
	if thread != "" && len(allRuns) > 0 {
		if latest := latestRunInThread(thread, allRuns); latest != nil {
			msgs, err := s.client.GetConversation(ctx, latest.ID)
			if err == nil && len(msgs) > 0 {
				return toViewMessages(msgs)
			}
		}
	}
	msgs, err := s.client.GetConversation(ctx, runID)
	if err != nil || len(msgs) == 0 {
		return nil
	}
	return toViewMessages(msgs)
}

// threadHistory was previously used to concatenate all prior conversations across
// runs in a thread. That produced duplicate turns because each run's
// conversation.json already includes history. Keep this helper unused for now.

func toViewMessages(msgs []ChatMessage) []views.ChatMessage {
	if len(msgs) == 0 {
		return nil
	}
	out := make([]views.ChatMessage, 0, len(msgs))
	for _, m := range msgs {
		out = append(out, views.ChatMessage{Role: m.Role, Content: m.Content})
	}
	return out
}

func parseRunTime(value string) time.Time {
	layouts := []string{
		"2006-01-02T15:04:05.000000Z",
		"2006-01-02T15:04:05.000Z",
		"2006-01-02T15:04:05Z",
	}
	for _, layout := range layouts {
		if t, err := time.Parse(layout, value); err == nil {
			return t
		}
	}
	return time.Time{}
}

func genID() string {
	var buf [8]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return ""
	}
	return hex.EncodeToString(buf[:])
}

// New chat form endpoint
func (s *Server) handleNewChatForm(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.withTimeout(r)
	defer cancel()
	selModel, modelOptions := s.modelOptions(ctx)
	thread := genID()
	_ = views.Render(w, views.ChatFormPartial(thread, selModel, modelOptions, ""))
	_ = views.Render(w, views.RunDetailReset())
}
