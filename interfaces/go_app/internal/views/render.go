package views

import (
	"context"
	"net/http"

	"github.com/a-h/templ"
)

func Render(w http.ResponseWriter, c templ.Component) error {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	return c.Render(context.Background(), w)
}
