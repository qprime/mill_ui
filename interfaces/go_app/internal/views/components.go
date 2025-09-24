package views

import (
	"context"
	"fmt"
	"html"
	"io"
	"strings"

	"github.com/a-h/templ"
)

func Page(data PageData) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		title := data.Title
		if title == "" {
			title = "ACE Console"
		}

		if _, err := io.WriteString(w, "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "<title>"+html.EscapeString(title)+"</title>"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "<script src=\"https://cdn.tailwindcss.com?plugins=forms,typography\"></script>"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "<link rel=\"stylesheet\" href=\"/static/css/main.css\">"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "<script src=\"https://unpkg.com/htmx.org@1.9.12\" defer></script>"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "<script>document.addEventListener('htmx:afterRequest',function(evt){if(evt.detail && evt.detail.elt && evt.detail.elt.dataset && evt.detail.elt.dataset.reset==='true'){evt.detail.elt.reset();}});</script>"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "</head><body class=\"bg-slate-950 text-slate-100 min-h-screen flex flex-col\">"); err != nil {
			return err
		}

		if _, err := io.WriteString(w, "<div class=\"flex flex-1 overflow-hidden\">"); err != nil {
			return err
		}
		if _, err := io.WriteString(w, sidebarHTML(data)); err != nil {
			return err
		}
		if _, err := io.WriteString(w, mainHTML(data)); err != nil {
			return err
		}
		if _, err := io.WriteString(w, "</div></body></html>"); err != nil {
			return err
		}
		return nil
	})
}

func sidebarHTML(data PageData) string {
	var b strings.Builder
	b.WriteString("<aside class=\"w-full max-w-xs border-r border-slate-800 bg-slate-950/70 overflow-y-auto\"><div class=\"p-6 space-y-6\">")
	b.WriteString("<header class=\"space-y-2\"><div class=\"flex items-center gap-3\"><span class=\"text-2xl\">♠︎</span><div><h1 class=\"text-xl font-semibold\">ACE Console</h1><p class=\"text-sm text-slate-400\">Chat-first runs with deterministic context.</p></div></div></header>")
	b.WriteString("<section><h2 class=\"text-sm font-semibold uppercase tracking-wide text-slate-400 mb-3\">Runs</h2>")
	b.WriteString(runListHTML(data.Runs, currentID(data.CurrentRun)))
	b.WriteString("</section>")
	b.WriteString("<section class=\"mt-6\"><div class=\"flex items-center justify-between mb-3\"><h2 class=\"text-sm font-semibold uppercase tracking-wide text-slate-400\">Machines</h2><button class=\"text-xs text-sky-400\" hx-get=\"/ace/hx/machines\" hx-target=\"#machine-list\" hx-swap=\"outerHTML\">Refresh</button></div>")
	b.WriteString(machineListHTML(data.Machines))
	b.WriteString("</section>")
	b.WriteString("<section class=\"mt-6\"><div class=\"flex items-center justify-between mb-3\"><h2 class=\"text-sm font-semibold uppercase tracking-wide text-slate-400\">Operate Policy</h2><button class=\"text-xs text-sky-400\" hx-get=\"/ace/hx/policy\" hx-target=\"#policy-table\" hx-swap=\"outerHTML\">Refresh</button></div>")
	b.WriteString(policyTableHTML(data.Policy))
	b.WriteString("</section>")
	b.WriteString("</div></aside>")
	return b.String()
}

func mainHTML(data PageData) string {
	var b strings.Builder
	b.WriteString("<main class=\"flex-1 flex flex-col bg-slate-950/40\"><div class=\"flex-1 overflow-y-auto p-8\">")
	if data.ErrorMessage != "" {
		b.WriteString("<div class=\"mb-4 rounded border border-red-500/60 bg-red-500/10 px-4 py-3 text-red-200\">" + html.EscapeString(data.ErrorMessage) + "</div>")
	}
	b.WriteString(runDetailHTML(data.CurrentRun, data.Runs, false))
	b.WriteString("</div>")
	b.WriteString(chatFormHTML())
	b.WriteString("</main>")
	return b.String()
}

func currentID(run *Run) string {
	if run == nil {
		return ""
	}
	return run.ID
}

func runListHTML(runs []Run, current string) string {
	var b strings.Builder
	b.WriteString("<div id=\"run-list\" class=\"space-y-2\" hx-trigger=\"runs-refresh from:body\" hx-get=\"/ace/hx/runs\" hx-target=\"#run-list\" hx-swap=\"outerHTML\">")
	if len(runs) == 0 {
		b.WriteString("<p class=\"text-sm text-slate-500\">No runs yet.</p></div>")
		return b.String()
	}
	for _, run := range runs {
		classes := []string{"w-full", "text-left", "px-3", "py-2", "rounded-md", "border", "border-slate-800", "bg-slate-900/40", "hover:border-sky-400", "transition"}
		if run.ID == current {
			classes = append(classes, "border-sky-500", "bg-sky-500/10")
		}
		fmt.Fprintf(&b, "<button data-run-id=\"%s\" class=\"%s\" hx-get=\"/ace/hx/runs/%s\" hx-target=\"#run-detail\" hx-swap=\"outerHTML\">",
			html.EscapeString(run.ID), strings.Join(classes, " "), html.EscapeString(run.ID))
		fmt.Fprintf(&b, "<div class=\"flex items-center justify-between\"><span class=\"text-sm font-medium\">%s</span><span class=\"text-xs text-slate-500\">%s</span></div>", html.EscapeString(run.Title), html.EscapeString(run.UpdatedLabel))
		fmt.Fprintf(&b, "<div class=\"text-xs uppercase tracking-wide text-slate-500 mt-1\">%s · %s</div>", html.EscapeString(strings.ToUpper(run.Mode)), html.EscapeString(run.Status))
		b.WriteString("</button>")
	}
	b.WriteString("</div>")
	return b.String()
}

func runDetailHTML(current *Run, runs []Run, includeOOB bool) string {
	var b strings.Builder
	b.WriteString("<div id=\"run-detail\">")
	if current == nil {
		b.WriteString("<p class=\"text-slate-400\">Select a run to view details.</p></div>")
		return b.String()
	}
	fmt.Fprintf(&b, "<header class=\"space-y-1 mb-6\"><h2 class=\"text-2xl font-semibold\">%s</h2>", html.EscapeString(current.Title))
	fmt.Fprintf(&b, "<p class=\"text-sm text-slate-400\">Run %s · %s · updated %s</p></header>", html.EscapeString(current.ID), html.EscapeString(strings.ToUpper(current.Mode)), html.EscapeString(current.UpdatedLabel))
	if current.ResultSummary != "" {
		fmt.Fprintf(&b, "<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Result</h3><div class=\"prose prose-invert max-w-none text-sm bg-slate-900/60 border border-slate-800 rounded-lg p-4 whitespace-pre-wrap\">%s</div></section>", html.EscapeString(current.ResultSummary))
	}
	if current.PlanSummary != "" {
		fmt.Fprintf(&b, "<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Plan</h3><div class=\"bg-slate-900/40 border border-slate-800 rounded-lg p-4 text-sm whitespace-pre-wrap\">%s</div></section>", html.EscapeString(current.PlanSummary))
	}
	if len(current.Commands) > 0 {
		b.WriteString("<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Commands</h3><ul class=\"space-y-1 text-sm\">")
		for _, cmd := range current.Commands {
			fmt.Fprintf(&b, "<li class=\"bg-slate-900/40 border border-slate-800 rounded px-3 py-2 font-mono text-xs\">%s</li>", html.EscapeString(cmd))
		}
		b.WriteString("</ul></section>")
	}
	if len(current.Tests) > 0 {
		b.WriteString("<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Tests</h3><ul class=\"list-disc list-inside text-sm text-slate-300 space-y-1\">")
		for _, test := range current.Tests {
			fmt.Fprintf(&b, "<li>%s</li>", html.EscapeString(test))
		}
		b.WriteString("</ul></section>")
	}
	if len(current.Artifacts) > 0 {
		b.WriteString("<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Artifacts</h3><ul class=\"list-disc list-outside ml-5 text-sm text-sky-400 space-y-1\">")
		for _, artifact := range current.Artifacts {
			fmt.Fprintf(&b, "<li><span>%s</span></li>", html.EscapeString(artifact))
		}
		b.WriteString("</ul></section>")
	}
	if current.Notes != "" {
		fmt.Fprintf(&b, "<section class=\"mb-6\"><h3 class=\"text-sm font-semibold text-slate-300 mb-2\">Notes</h3><p class=\"text-sm text-slate-300\">%s</p></section>", html.EscapeString(current.Notes))
	}
	if len(current.Tags) > 0 {
		b.WriteString("<div class=\"flex flex-wrap gap-2 text-xs text-slate-400\">")
		for _, tag := range current.Tags {
			fmt.Fprintf(&b, "<span class=\"px-2 py-1 rounded border border-slate-700 bg-slate-900/40\">%s</span>", html.EscapeString(tag))
		}
		b.WriteString("</div>")
	}
	b.WriteString("</div>")
	if includeOOB {
		b.WriteString(runListOOB(runs, current.ID))
	}
	return b.String()
}

func runListOOB(runs []Run, current string) string {
	list := runListHTML(runs, current)
	return strings.Replace(list, "<div id=\"run-list\"", "<div id=\"run-list\" hx-swap-oob=\"outerHTML\"", 1)
}

func machineListHTML(machines []Machine) string {
	var b strings.Builder
	b.WriteString("<div id=\"machine-list\" class=\"space-y-2\">")
	if len(machines) == 0 {
		b.WriteString("<p class=\"text-sm text-slate-500\">No machines configured.</p></div>")
		return b.String()
	}
	for _, machine := range machines {
		fmt.Fprintf(&b, "<div class=\"border border-slate-800 rounded-lg p-3 bg-slate-900/40\"><div class=\"flex items-center justify-between\"><span class=\"font-semibold text-sm\">%s</span><span class=\"text-xs uppercase text-slate-500\">%s</span></div>", html.EscapeString(machine.Name), html.EscapeString(machine.Type))
		fmt.Fprintf(&b, "<div class=\"text-xs text-slate-400 mt-1\">%s</div>", html.EscapeString(machine.Workspace))
		if machine.Host != "" {
			fmt.Fprintf(&b, "<div class=\"text-xs text-slate-500\">%s</div>", html.EscapeString(machine.Host))
		}
		if machine.Notes != "" {
			fmt.Fprintf(&b, "<div class=\"text-xs text-slate-400 mt-1\">%s</div>", html.EscapeString(machine.Notes))
		}
		b.WriteString("</div>")
	}
	b.WriteString("</div>")
	return b.String()
}

func policyTableHTML(entries []PolicyEntry) string {
	var b strings.Builder
	b.WriteString("<div id=\"policy-table\" class=\"border border-slate-800 rounded-lg overflow-hidden text-sm\">")
	if len(entries) == 0 {
		b.WriteString("<div class=\"p-3 text-slate-500\">No policy entries.</div></div>")
		return b.String()
	}
	b.WriteString("<table class=\"min-w-full divide-y divide-slate-800\"><tbody class=\"divide-y divide-slate-800\">")
	for _, entry := range entries {
		fmt.Fprintf(&b, "<tr><td class=\"px-3 py-2 text-slate-300\">%s</td><td class=\"px-3 py-2 text-right\"><span class=\"px-2 py-1 rounded text-xs bg-slate-900/40 border border-slate-800\">%s</span></td></tr>", html.EscapeString(entry.Key), html.EscapeString(capitalize(entry.Value)))
	}
	b.WriteString("</tbody></table></div>")
	return b.String()
}

func chatFormHTML() string {
	return `<form id="chat-form" class="border-t border-slate-800 bg-slate-950/80 p-6 space-y-4" hx-post="/ace/hx/chat" hx-target="#run-detail" hx-swap="outerHTML" data-reset="true">
	<label class="block text-sm text-slate-300 font-medium" for="chat-input">Ask ACE</label>
	<textarea id="chat-input" name="text" required rows="3" class="w-full rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500" placeholder="Ask ACE anything about cliff_ai…"></textarea>
	<div class="flex items-center justify-between">
		<span class="text-xs text-slate-500">Ctrl+Enter to submit</span>
		<button type="submit" class="inline-flex items-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow hover:bg-sky-400 transition">Send</button>
	</div>
	<span class="htmx-indicator text-xs text-slate-400">Sending…</span>
</form>`
}

func RunListPartial(runs []Run, current string) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, runListHTML(runs, current))
		return err
	})
}

func RunDetailPartial(run *Run, runs []Run) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, runDetailHTML(run, runs, true))
		return err
	})
}

func MachineListPartial(machines []Machine) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, machineListHTML(machines))
		return err
	})
}

func PolicyPartial(entries []PolicyEntry) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, policyTableHTML(entries))
		return err
	})
}

func capitalize(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	if s == "" {
		return s
	}
	runes := []rune(s)
	runes[0] = []rune(strings.ToUpper(string(runes[0])))[0]
	return string(runes)
}
