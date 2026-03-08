package security

import (
	"bytes"
	"encoding/base64"
	"testing"
)

func TestEncryptDecryptStringRoundTrip(t *testing.T) {
	key := base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))

	ciphertext, err := EncryptString(key, "secret-token")
	if err != nil {
		t.Fatalf("encrypt string: %v", err)
	}
	if ciphertext == "secret-token" {
		t.Fatalf("expected ciphertext to differ from plaintext")
	}

	plaintext, err := DecryptString(key, ciphertext)
	if err != nil {
		t.Fatalf("decrypt string: %v", err)
	}
	if plaintext != "secret-token" {
		t.Fatalf("expected decrypted plaintext, got %q", plaintext)
	}
}

func TestDecodeEncryptionKeyRequiresThirtyTwoBytes(t *testing.T) {
	shortKey := base64.StdEncoding.EncodeToString([]byte("too-short"))
	if _, err := DecodeEncryptionKey(shortKey); err == nil {
		t.Fatalf("expected invalid short key to fail")
	}
}

func TestSignAndVerifyCookie(t *testing.T) {
	signed, err := SignCookie("app-secret", "session-123")
	if err != nil {
		t.Fatalf("sign cookie: %v", err)
	}

	value, err := VerifySignedCookie("app-secret", signed)
	if err != nil {
		t.Fatalf("verify signed cookie: %v", err)
	}
	if value != "session-123" {
		t.Fatalf("expected verified cookie value, got %q", value)
	}

	if _, err := VerifySignedCookie("wrong-secret", signed); err == nil {
		t.Fatalf("expected wrong secret to fail verification")
	}
}
