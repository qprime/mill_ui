package views

type Run struct {
	ID            string
	Mode          string
	Status        string
	Title         string
	UpdatedLabel  string
	ResultSummary string
	PlanSummary   string
	Commands      []string
	Tests         []string
	Artifacts     []string
	Notes         string
	Tags          []string
	Conversation  []ChatMessage
}

type Machine struct {
	Name      string
	Type      string
	Host      string
	Workspace string
	Notes     string
}

type PolicyEntry struct {
	Key   string
	Value string
}

type PageData struct {
	Title        string
	Runs         []Run
	CurrentRun   *Run
	Machines     []Machine
	Policy       []PolicyEntry
	ErrorMessage string
	// Chat configuration
	SelectedModel string
	ModelOptions  []ModelOption
	Thread        string
	ContinueRunID string
}

type ChatMessage struct {
	Role    string
	Content string
}

type ModelOption struct {
	Value    string
	Label    string
	Group    string
	Disabled bool
}
