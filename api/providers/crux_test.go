package providers

import "testing"

func TestNormalizeCruxToken(t *testing.T) {
	testCases := map[string]string{
		"":                     "",
		" raw-token ":          "raw-token",
		"Bearer raw-token":     "raw-token",
		"bearer raw-token ":    "raw-token",
		"  BeArEr raw-token  ": "raw-token",
		"Bearer":               "Bearer",
		"Bearerraw-token":      "Bearerraw-token",
	}

	for input, expected := range testCases {
		if actual := normalizeCruxToken(input); actual != expected {
			t.Fatalf("normalizeCruxToken(%q) = %q, want %q", input, actual, expected)
		}
	}
}
