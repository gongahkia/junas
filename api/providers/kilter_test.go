package providers

import "testing"

func TestParseKilterClimbID_Valid(t *testing.T) {
	boardID, uuid, err := parseKilterClimbID("kilter:14:abc-123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if boardID != 14 {
		t.Fatalf("boardID = %d, want 14", boardID)
	}
	if uuid != "abc-123" {
		t.Fatalf("uuid = %q, want %q", uuid, "abc-123")
	}
}

func TestParseKilterClimbID_InvalidPrefix(t *testing.T) {
	_, _, err := parseKilterClimbID("crux:123")
	if err == nil {
		t.Fatal("expected error for non-kilter prefix, got nil")
	}
}

func TestParseKilterClimbID_Empty(t *testing.T) {
	_, _, err := parseKilterClimbID("")
	if err == nil {
		t.Fatal("expected error for empty string, got nil")
	}
}

func TestParseKilterContext_MissingBoardID(t *testing.T) {
	_, _, err := parseKilterContext("", map[string]string{"angle": "40"})
	if err == nil {
		t.Fatal("expected error for missing board id, got nil")
	}
}

func TestParseKilterContext_UnsupportedAngle(t *testing.T) {
	_, _, err := parseKilterContext("1", map[string]string{"angle": "999"})
	if err == nil {
		t.Fatal("expected error for unsupported angle 999, got nil")
	}
}
