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
			title = "ACE Chat"
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
		if _, err := io.WriteString(w, "<script>document.addEventListener('htmx:afterRequest',function(evt){if(evt.detail && evt.detail.elt && evt.detail.elt.dataset && evt.detail.elt.dataset.reset==='true'){evt.detail.elt.reset();}});\nwindow.aceLive={src:null};\nwindow.aceStartLog=function(runId){try{if(window.aceLive.src){window.aceLive.src.close();}var el=document.getElementById('live-log');if(el){el.textContent='';}var es=new EventSource('/ace/sse/'+runId);window.aceLive.src=es;es.addEventListener('log',function(ev){try{var d=JSON.parse(ev.data);if(el){el.textContent=d.text||'';el.scrollTop=el.scrollHeight;}}catch(e){if(el){el.textContent=ev.data;}}});es.addEventListener('message',function(ev){if(el){el.textContent+=(ev.data||'')+'\n';el.scrollTop=el.scrollHeight;}});es.addEventListener('heartbeat',function(_){/*no-op*/});es.onerror=function(){/* keep open; server sets retry */};}catch(e){console.error(e);}};\nwindow.aceStopLog=function(){try{if(window.aceLive.src){window.aceLive.src.close();window.aceLive.src=null;}}catch(e){}}</script>"); err != nil {
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
	b.WriteString("<header class=\"space-y-2\"><div class=\"flex items-center justify-between gap-3\"><div class=\"flex items-center gap-3\"><span class=\"text-2xl\">♠︎</span><div><h1 class=\"text-xl font-semibold\">ACE Chat</h1><p class=\"text-sm text-slate-400\">Simple chat with memory context.</p></div></div><button class=\"text-xs rounded-md border border-slate-700 px-2 py-1 hover:border-sky-400 transition\" hx-get=\"/ace/hx/new\" hx-target=\"#chat-form\" hx-swap=\"outerHTML\">New Chat</button></div></header>")
	b.WriteString("<section><h2 class=\"text-sm font-semibold uppercase tracking-wide text-slate-400 mb-3\">Chats</h2>")
	b.WriteString(runListHTML(data.Runs, currentID(data.CurrentRun)))
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
	b.WriteString(chatFormHTML(data.Thread, data.SelectedModel, data.ModelOptions, data.ContinueRunID, false))
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
	fmt.Fprintf(&b, "<header class=\"space-y-1 mb-4\"><h2 class=\"text-2xl font-semibold\">%s</h2>", html.EscapeString(current.Title))
	fmt.Fprintf(&b, "<p class=\"text-sm text-slate-400\">Chat %s · updated %s</p></header>", html.EscapeString(current.ID), html.EscapeString(current.UpdatedLabel))
	// Live log controls and container
	fmt.Fprintf(&b, "<div class=\"mb-3 flex items-center gap-2\"><button type=\"button\" class=\"text-xs rounded-md border border-slate-700 px-2 py-1 hover:border-sky-400 transition\" onclick=\"aceStartLog('%s')\">Live Log</button><button type=\"button\" class=\"text-xs rounded-md border border-slate-700 px-2 py-1 hover:border-sky-400 transition\" onclick=\"aceStopLog()\">Stop</button></div>", html.EscapeString(current.ID))
	b.WriteString("<pre id=\"live-log\" class=\"text-xs bg-slate-900/60 border border-slate-800 rounded-lg p-3 whitespace-pre-wrap overflow-y-auto max-h-64\"></pre>")

	// Chat transcript at the top
	b.WriteString("<section class=\"mb-6 space-y-3\">")
	if len(current.Conversation) == 0 && current.ResultSummary != "" {
		// fallback: show summary if no conversation captured
		fmt.Fprintf(&b, "<div class=\"prose prose-invert max-w-none text-sm bg-slate-900/60 border border-slate-800 rounded-lg p-4 whitespace-pre-wrap\">%s</div>", html.EscapeString(current.ResultSummary))
	}
	for _, m := range current.Conversation {
		role := strings.ToLower(strings.TrimSpace(m.Role))
		bubble := "bg-slate-900/60 border-slate-800"
		align := "justify-start"
		label := "User"
		if role == "assistant" {
			bubble = "bg-sky-500/10 border-sky-500/60"
			align = "justify-start"
			label = "Assistant"
		} else if role == "system" {
			bubble = "bg-slate-900/40 border-slate-700"
			align = "justify-center"
			label = "System"
		}
		fmt.Fprintf(&b, "<div class=\"flex %s\"><div class=\"max-w-3xl w-fit border %s rounded-lg px-4 py-3\"><div class=\"text-xs text-slate-400 mb-1\">%s</div><div class=\"whitespace-pre-wrap text-sm\">%s</div></div></div>", align, bubble, html.EscapeString(label), html.EscapeString(m.Content))
	}
	b.WriteString("</section>")
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

func chatFormHTML(thread, selectedModel string, options []ModelOption, continueID string, oob bool) string {
	var b strings.Builder
	// Outer form
	if oob {
		b.WriteString(`<form id="chat-form" hx-swap-oob="outerHTML" class="border-t border-slate-800 bg-slate-950/80 p-6 space-y-4" hx-post="/ace/hx/chat" hx-target="#run-detail" hx-swap="outerHTML" data-reset="true">`)
	} else {
		b.WriteString(`<form id="chat-form" class="border-t border-slate-800 bg-slate-950/80 p-6 space-y-4" hx-post="/ace/hx/chat" hx-target="#run-detail" hx-swap="outerHTML" data-reset="true">`)
	}
	b.WriteString(`<div class="flex items-center justify-between gap-3">
        <label class="block text-sm text-slate-300 font-medium" for="chat-input">Ask ACE</label>
        <div class="flex items-center gap-2">
            <label class="text-xs text-slate-400" for="model">Model</label>
            <select id="model" name="model" class="text-xs rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500">`)
	if len(options) == 0 {
		options = []ModelOption{{Value: "gpt-5", Label: "gpt-5", Group: "OpenAI API"}}
	}
	if selectedModel == "" {
		for _, opt := range options {
			if !opt.Disabled {
				selectedModel = opt.Value
				break
			}
		}
		if selectedModel == "" {
			selectedModel = options[0].Value
		}
	}
	currentGroup := ""
	for _, opt := range options {
		group := opt.Group
		if group == "" {
			group = "Other"
		}
		if group != currentGroup {
			if currentGroup != "" {
				b.WriteString("</optgroup>")
			}
			fmt.Fprintf(&b, `<optgroup label="%s">`, html.EscapeString(group))
			currentGroup = group
		}
		attrs := ""
		if opt.Disabled {
			attrs += " disabled"
		}
		if opt.Value == selectedModel {
			attrs += " selected"
		}
		fmt.Fprintf(&b, `<option value="%s"%s>%s</option>`, html.EscapeString(opt.Value), attrs, html.EscapeString(opt.Label))
	}
	if currentGroup != "" {
		b.WriteString("</optgroup>")
	}
	b.WriteString(`</select>
        </div>
    </div>`)
	// Textarea
	b.WriteString(`<textarea id="chat-input" name="text" required rows="3" class="w-full rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500" placeholder="Ask ACE anything about cliff_ai…"></textarea>`)
	// Controls
	b.WriteString(`<div class="flex items-center justify-between">
        <span class="text-xs text-slate-500">Ctrl+Enter to submit</span>
        <div class="flex items-center gap-2">
            <button type="submit" class="inline-flex items-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow hover:bg-sky-400 transition">Send</button>
        </div>
    </div>`)
	// Hidden fields
	if thread != "" {
		fmt.Fprintf(&b, `<input type="hidden" name="thread" value="%s"/>`, html.EscapeString(thread))
	}
	if continueID != "" {
		fmt.Fprintf(&b, `<input type="hidden" name="continue" value="%s"/>`, html.EscapeString(continueID))
	}
	b.WriteString(`<span class="htmx-indicator text-xs text-slate-400">Sending…</span></form>`)
	return b.String()
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

func PlanRequired(message string) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		if message == "" {
			message = "Plan preview is required before ACE can execute this request."
		}
		html := "<div id=\"run-detail\" class=\"space-y-4\"><div class=\"rounded border border-amber-500/60 bg-amber-500/10 px-4 py-3 text-amber-200\">" + html.EscapeString(message) + "</div><p class=\"text-sm text-slate-400\">Generate a plan from the CLI or promote the plan from the Runs list before resubmitting.</p></div>"
		_, err := io.WriteString(w, html)
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

// Chat form partials -------------------------------------------------
func ChatFormPartial(thread, selectedModel string, options []ModelOption, continueID string) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, chatFormHTML(thread, selectedModel, options, continueID, false))
		return err
	})
}

func ChatFormOOB(thread, selectedModel string, options []ModelOption, continueID string) templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, chatFormHTML(thread, selectedModel, options, continueID, true))
		return err
	})
}

func RunDetailReset() templ.Component {
	return templ.ComponentFunc(func(ctx context.Context, w io.Writer) error {
		_ = ctx
		_, err := io.WriteString(w, emptyRunDetailHTML(true))
		return err
	})
}

func emptyRunDetailHTML(oob bool) string {
	attr := ""
	if oob {
		attr = " hx-swap-oob=\"outerHTML\""
	}
	return `<div id="run-detail"` + attr + ` class="space-y-4"><p class="text-slate-400">Start a new chat to begin the narrative.</p></div>`
}
