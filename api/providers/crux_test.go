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

func TestParseCruxClimbID_Valid(t *testing.T) {
	id, err := parseCruxClimbID("crux:456")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != 456 {
		t.Fatalf("id = %d, want 456", id)
	}
}

func TestParseCruxClimbID_InvalidPrefix(t *testing.T) {
	_, err := parseCruxClimbID("kilter:14:uuid")
	if err == nil {
		t.Fatal("expected error for non-crux prefix, got nil")
	}
}

func TestDecodeOffsetCursor_Empty(t *testing.T) {
	offset, err := decodeOffsetCursor("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if offset != 0 {
		t.Fatalf("offset = %d, want 0", offset)
	}
}

func TestDecodeOffsetCursor_Valid(t *testing.T) {
	cursor := encodeOffsetCursor(42)
	offset, err := decodeOffsetCursor(cursor)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if offset != 42 {
		t.Fatalf("offset = %d, want 42", offset)
	}
}

func TestDecodeOffsetCursor_Negative(t *testing.T) {
	cursor := encodeOffsetCursor(-5)
	_, err := decodeOffsetCursor(cursor)
	if err == nil {
		t.Fatal("expected error for negative offset, got nil")
	}
}

func TestSortCruxClimbs_Newest(t *testing.T) {
	climbs := []cruxClimb{
		{ID: 1, CreatedAt: "2024-01-01", NumberOfSends: 10},
		{ID: 2, CreatedAt: "2024-06-01", NumberOfSends: 5},
		{ID: 3, CreatedAt: "2024-03-01", NumberOfSends: 20},
	}
	sortCruxClimbs(climbs, "newest")
	if climbs[0].ID != 2 || climbs[1].ID != 3 || climbs[2].ID != 1 {
		t.Fatalf("newest sort order wrong: got IDs [%d, %d, %d], want [2, 3, 1]",
			climbs[0].ID, climbs[1].ID, climbs[2].ID)
	}
}

func TestSortCruxClimbs_Popular(t *testing.T) {
	climbs := []cruxClimb{
		{ID: 1, CreatedAt: "2024-01-01", NumberOfSends: 10},
		{ID: 2, CreatedAt: "2024-06-01", NumberOfSends: 5},
		{ID: 3, CreatedAt: "2024-03-01", NumberOfSends: 20},
	}
	sortCruxClimbs(climbs, "popular")
	if climbs[0].ID != 3 || climbs[1].ID != 1 || climbs[2].ID != 2 {
		t.Fatalf("popular sort order wrong: got IDs [%d, %d, %d], want [3, 1, 2]",
			climbs[0].ID, climbs[1].ID, climbs[2].ID)
	}
}
