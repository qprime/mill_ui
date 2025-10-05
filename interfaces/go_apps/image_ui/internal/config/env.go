package config

import "os"

func APIKey() string {
	return os.Getenv("OPENAI_API_KEY")
}
