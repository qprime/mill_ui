package httpserver

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"strings"
	"time"
)

type Client struct {
	baseURL    *url.URL
	httpClient *http.Client
}

type requestOption func(*http.Request)

func NewClient(base string, timeout time.Duration) *Client {
	u, err := url.Parse(base)
	if err != nil {
		u, _ = url.Parse("http://127.0.0.1:8080/ace")
	}
	if !u.IsAbs() {
		u.Scheme = "http"
	}
	hc := &http.Client{Timeout: timeout}
	if strings.EqualFold(os.Getenv("ACE_TLS_INSECURE"), "true") || os.Getenv("ACE_TLS_INSECURE") == "1" {
		hc.Transport = &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	}
	return &Client{baseURL: u, httpClient: hc}
}

func (c *Client) newRequest(ctx context.Context, method, endpoint string, body io.Reader, opts ...requestOption) (*http.Request, error) {
	u := *c.baseURL
	u.Path = strings.TrimSuffix(c.baseURL.Path, "/") + path.Clean("/"+endpoint)

	req, err := http.NewRequestWithContext(ctx, method, u.String(), body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	for _, opt := range opts {
		opt(req)
	}
	return req, nil
}

func withJSONBody(payload any) requestOption {
	return func(r *http.Request) {
		buf := new(bytes.Buffer)
		enc := json.NewEncoder(buf)
		enc.SetEscapeHTML(true)
		_ = enc.Encode(payload)
		r.Body = io.NopCloser(buf)
		r.ContentLength = int64(buf.Len())
		r.GetBody = func() (io.ReadCloser, error) { return io.NopCloser(bytes.NewReader(buf.Bytes())), nil }
		r.Header.Set("Content-Type", "application/json")
	}
}

func (c *Client) do(req *http.Request, v any) (*http.Response, error) {
	res, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	if res.StatusCode >= 400 {
		defer res.Body.Close()
		b, _ := io.ReadAll(io.LimitReader(res.Body, 4096))
		return nil, fmt.Errorf("backend error %s: %s", res.Status, strings.TrimSpace(string(b)))
	}
	if v == nil {
		return res, nil
	}
	dec := json.NewDecoder(res.Body)
	if err := dec.Decode(v); err != nil && !errors.Is(err, io.EOF) {
		res.Body.Close()
		return nil, err
	}
	res.Body.Close()
	return res, nil
}

func (c *Client) ListRuns(ctx context.Context) ([]Run, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/runs", nil)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Runs []Run `json:"runs"`
	}
	if _, err := c.do(req, &payload); err != nil {
		return nil, err
	}
	return payload.Runs, nil
}

func (c *Client) GetRun(ctx context.Context, id string) (*Run, error) {
	endpoint := fmt.Sprintf("/runs/%s/summary", url.PathEscape(id))
	req, err := c.newRequest(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Run Run `json:"run"`
	}
	if _, err := c.do(req, &payload); err != nil {
		return nil, err
	}
	return &payload.Run, nil
}

func (c *Client) ListMachines(ctx context.Context) ([]Machine, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/machines", nil)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Machines []Machine `json:"machines"`
	}
	if _, err := c.do(req, &payload); err != nil {
		return nil, err
	}
	return payload.Machines, nil
}

func (c *Client) FetchPolicy(ctx context.Context) (Policy, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/operate/policy", nil)
	if err != nil {
		return Policy{}, err
	}
	var payload struct {
		Effective map[string]string `json:"effective"`
	}
	if _, err := c.do(req, &payload); err != nil {
		return Policy{}, err
	}
	return NewPolicy(payload.Effective), nil
}

var ErrPlanRequired = errors.New("plan required before execution")

func (c *Client) CreateChatRun(ctx context.Context, text string) (*Run, error) {
	body := map[string]any{
		"brief": map[string]any{
			"mode":         "ideate",
			"text":         text,
			"machines":     []string{"skylink"},
			"tags":         []string{"chat"},
			"plan_preview": "skip",
		},
		"execute": true,
	}
	req, err := c.newRequest(ctx, http.MethodPost, "/runs", nil, withJSONBody(body))
	if err != nil {
		return nil, err
	}
	var payload struct {
		Run Run `json:"run"`
	}
	res, err := c.do(req, &payload)
	if err != nil {
		return nil, err
	}
	if res.StatusCode == http.StatusAccepted {
		return nil, ErrPlanRequired
	}
	return &payload.Run, nil
}

// CreateChatRunWith allows passing prior conversation, tags, and explicit model.
func (c *Client) CreateChatRunWith(ctx context.Context, text string, conversation []ChatMessage, tags []string, model string) (*Run, error) {
	if len(tags) == 0 {
		tags = []string{"chat"}
	}
	body := map[string]any{
		"brief": map[string]any{
			"mode":         "ideate",
			"text":         text,
			"machines":     []string{"skylink"},
			"tags":         tags,
			"plan_preview": "skip",
			"context": map[string]any{
				"include":         true,
				"scope":           "auto",
				"include_persona": true,
			},
		},
		"execute": true,
	}
	if model != "" {
		if m, ok := body["brief"].(map[string]any); ok {
			m["model"] = model
		}
	}
	if len(conversation) > 0 {
		body["conversation"] = conversation
	}
	req, err := c.newRequest(ctx, http.MethodPost, "/runs", nil, withJSONBody(body))
	if err != nil {
		return nil, err
	}
	var payload struct {
		Run Run `json:"run"`
	}
	res, err := c.do(req, &payload)
	if err != nil {
		return nil, err
	}
	if res.StatusCode == http.StatusAccepted {
		return nil, ErrPlanRequired
	}
	return &payload.Run, nil
}

// ---- Chat transcript helpers ----

type artifactsResponse struct {
	Artifacts []string `json:"artifacts"`
}

// ListArtifacts fetches the artifact paths for a run.
func (c *Client) ListArtifacts(ctx context.Context, id string) ([]string, error) {
	endpoint := fmt.Sprintf("/runs/%s/artifacts", url.PathEscape(id))
	req, err := c.newRequest(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	var payload artifactsResponse
	if _, err := c.do(req, &payload); err != nil {
		return nil, err
	}
	return payload.Artifacts, nil
}

// GetRunFile reads the raw file content for a given artifact path.
func (c *Client) GetRunFile(ctx context.Context, id string, relPath string) (string, error) {
	endpoint := fmt.Sprintf("/runs/%s/file", url.PathEscape(id))
	req, err := c.newRequest(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return "", err
	}
	q := req.URL.Query()
	q.Set("path", relPath)
	req.URL.RawQuery = q.Encode()
	res, err := c.do(req, nil)
	if err != nil {
		return "", err
	}
	defer res.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(res.Body, 1<<20))
	return string(b), nil
}

// StreamSSE opens a streaming connection (no timeout) to an endpoint and returns the body.
func (c *Client) StreamSSE(ctx context.Context, endpoint string) (io.ReadCloser, *http.Response, error) {
	u := *c.baseURL
	u.Path = strings.TrimSuffix(c.baseURL.Path, "/") + path.Clean("/"+endpoint)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, nil, err
	}
	req.Header.Set("Accept", "text/event-stream")

	// Clone transport if present to preserve TLS settings
	var hc *http.Client
	if c.httpClient != nil && c.httpClient.Transport != nil {
		hc = &http.Client{Transport: c.httpClient.Transport}
	} else {
		hc = &http.Client{}
	}
	// No timeout for stream; rely on ctx cancellation
	hc.Timeout = 0

	res, err := hc.Do(req)
	if err != nil {
		return nil, nil, err
	}
	if res.StatusCode >= 400 {
		defer res.Body.Close()
		b, _ := io.ReadAll(io.LimitReader(res.Body, 4096))
		return nil, res, fmt.Errorf("backend error %s: %s", res.Status, strings.TrimSpace(string(b)))
	}
	return res.Body, res, nil
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// GetConversation loads the conversation messages for a chat run if present.
func (c *Client) GetConversation(ctx context.Context, id string) ([]ChatMessage, error) {
	artifacts, err := c.ListArtifacts(ctx, id)
	if err != nil {
		return nil, err
	}
	var convPath string
	for _, p := range artifacts {
		if strings.HasSuffix(strings.ToLower(p), "/conversation.json") || strings.HasSuffix(strings.ToLower(p), "conversation.json") {
			convPath = p
			break
		}
	}
	if convPath == "" {
		return nil, nil
	}
	raw, err := c.GetRunFile(ctx, id, convPath)
	if err != nil {
		return nil, err
	}
	var messages []ChatMessage
	if err := json.Unmarshal([]byte(raw), &messages); err != nil {
		return nil, err
	}
	return messages, nil
}

// Router config -----------------------------------
type RouterConfigResponse struct {
	Config RouterConfig `json:"config"`
	Source string       `json:"source"`
}

type RouterConfig struct {
	TaskTypes map[string]TaskType `json:"task_types"`
	Providers map[string]Provider `json:"providers"`
}

type TaskType struct {
	Provider string `json:"provider"`
	Stream   bool   `json:"stream"`
}

type Provider struct {
	Model           string   `json:"model"`
	Temperature     *float64 `json:"temperature,omitempty"`
	MaxPromptTokens *int     `json:"max_prompt_tokens,omitempty"`
	MaxOutputTokens *int     `json:"max_output_tokens,omitempty"`
	Fallback        *bool    `json:"fallback,omitempty"`
	Stream          *bool    `json:"stream,omitempty"`
}

func (c *Client) FetchRouterConfig(ctx context.Context) (RouterConfig, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/config/router", nil)
	if err != nil {
		return RouterConfig{}, err
	}
	var payload RouterConfigResponse
	if _, err := c.do(req, &payload); err != nil {
		return RouterConfig{}, err
	}
	return payload.Config, nil
}
