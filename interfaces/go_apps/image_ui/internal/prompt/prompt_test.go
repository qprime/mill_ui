package prompt

import (
	"testing"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/personas"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/styles"
)

func TestAssemble(t *testing.T) {
	p := personas.Persona{Genre: "baroque", PromptingStyle: "high contrast"}
	s := styles.Style{MachinabilityPrompt: "avoid thin lines"}
	got := Assemble("floral", p, s)
	want := "floral, in the style of baroque. high contrast. avoid thin lines"
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}
