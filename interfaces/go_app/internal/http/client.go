package httpserver

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
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
	return &Client{
		baseURL: u,
		httpClient: &http.Client{Timeout: timeout},
	}
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

func (c *Client) do(req *http.Request, v any) error {
	res, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode >= 400 {
		b, _ := io.ReadAll(io.LimitReader(res.Body, 4096))
		return fmt.Errorf("backend error %s: %s", res.Status, strings.TrimSpace(string(b)))
	}
	if v == nil {
		return nil
	}
	dec := json.NewDecoder(res.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(v)
}

func (c *Client) ListRuns(ctx context.Context) ([]Run, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/runs", nil)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Runs []Run `json:"runs"`
	}
	if err := c.do(req, &payload); err != nil {
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
	if err := c.do(req, &payload); err != nil {
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
	if err := c.do(req, &payload); err != nil {
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
	if err := c.do(req, &payload); err != nil {
		return Policy{}, err
	}
	return NewPolicy(payload.Effective), nil
}

func (c *Client) CreateChatRun(ctx context.Context, text string) (*Run, error) {
	body := map[string]any{
		"brief": map[string]any{
			"mode":     "ideate",
			"text":     text,
			"machines": []string{"skylink"},
			"tags":     []string{"chat"},
		},
	}
	req, err := c.newRequest(ctx, http.MethodPost, "/runs", nil, withJSONBody(body))
	if err != nil {
		return nil, err
	}
	var payload struct {
		Run Run `json:"run"`
	}
	if err := c.do(req, &payload); err != nil {
		return nil, err
	}
	return &payload.Run, nil
}
