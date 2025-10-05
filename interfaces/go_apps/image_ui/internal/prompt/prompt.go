package prompt

import (
	"fmt"

	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/personas"
	"github.com/squinlan/cliff_ai/interfaces/go_apps/image_ui/internal/styles"
)

func Assemble(subject string, persona personas.Persona, style styles.Style) string {
	return fmt.Sprintf("%s, in the style of %s. %s. %s", subject, persona.Genre, persona.PromptingStyle, style.MachinabilityPrompt)
}
