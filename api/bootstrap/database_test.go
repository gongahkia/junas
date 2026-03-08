package bootstrap

import (
	"archive/zip"
	"bytes"
	"testing"
)

func TestExtractBaseDatabaseFromRootArchive(t *testing.T) {
	databaseBytes := []byte("root-db")
	bundleBytes := buildZipArchive(t, map[string][]byte{
		kilterAssetPath: databaseBytes,
	})

	extractedBytes, err := ExtractBaseDatabase(bundleBytes)
	if err != nil {
		t.Fatalf("ExtractBaseDatabase returned error: %v", err)
	}
	if !bytes.Equal(extractedBytes, databaseBytes) {
		t.Fatalf("expected root database bytes %q, got %q", databaseBytes, extractedBytes)
	}
}

func TestExtractBaseDatabaseFromNestedAPK(t *testing.T) {
	databaseBytes := []byte("nested-db")
	nestedAPKBytes := buildZipArchive(t, map[string][]byte{
		kilterAssetPath: databaseBytes,
	})
	bundleBytes := buildZipArchive(t, map[string][]byte{
		"com.auroraclimbing.kilterboard.apk": nestedAPKBytes,
	})

	extractedBytes, err := ExtractBaseDatabase(bundleBytes)
	if err != nil {
		t.Fatalf("ExtractBaseDatabase returned error: %v", err)
	}
	if !bytes.Equal(extractedBytes, databaseBytes) {
		t.Fatalf("expected nested database bytes %q, got %q", databaseBytes, extractedBytes)
	}
}

func buildZipArchive(t *testing.T, files map[string][]byte) []byte {
	t.Helper()

	var archive bytes.Buffer
	zipWriter := zip.NewWriter(&archive)
	for fileName, fileContents := range files {
		fileWriter, err := zipWriter.Create(fileName)
		if err != nil {
			t.Fatalf("create zip entry %s: %v", fileName, err)
		}
		if _, err := fileWriter.Write(fileContents); err != nil {
			t.Fatalf("write zip entry %s: %v", fileName, err)
		}
	}
	if err := zipWriter.Close(); err != nil {
		t.Fatalf("close zip writer: %v", err)
	}

	return archive.Bytes()
}
