package security

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"strings"
)

func NewOpaqueToken() (string, error) {
	raw := make([]byte, 24)
	if _, err := rand.Read(raw); err != nil {
		return "", fmt.Errorf("generate opaque token: %w", err)
	}

	return base64.RawURLEncoding.EncodeToString(raw), nil
}

func SignCookie(secret string, value string) (string, error) {
	if strings.TrimSpace(secret) == "" {
		return "", fmt.Errorf("cookie secret is required")
	}

	mac := hmac.New(sha256.New, []byte(secret))
	if _, err := mac.Write([]byte(value)); err != nil {
		return "", fmt.Errorf("sign cookie: %w", err)
	}

	signature := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	return value + "." + signature, nil
}

func VerifySignedCookie(secret string, signed string) (string, error) {
	if strings.TrimSpace(secret) == "" {
		return "", fmt.Errorf("cookie secret is required")
	}

	parts := strings.Split(signed, ".")
	if len(parts) != 2 {
		return "", fmt.Errorf("invalid signed cookie format")
	}

	value, signature := parts[0], parts[1]
	expected, err := SignCookie(secret, value)
	if err != nil {
		return "", err
	}

	expectedParts := strings.Split(expected, ".")
	if !hmac.Equal([]byte(signature), []byte(expectedParts[1])) {
		return "", fmt.Errorf("invalid cookie signature")
	}

	return value, nil
}
