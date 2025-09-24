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
}
