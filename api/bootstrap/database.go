package bootstrap

import (
	"archive/zip"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	kilterBundleURL = "https://d.apkpure.net/b/APK/com.auroraclimbing.kilterboard?version=latest"
	kilterAssetPath = "assets/db.sqlite3"
)

var defaultHTTPClient = &http.Client{Timeout: 2 * time.Minute}

func DownloadBaseDatabase(ctx context.Context, outputPath string) error {
	bundle, err := downloadBundle(ctx, defaultHTTPClient, kilterBundleURL)
	if err != nil {
		return err
	}

	databaseBytes, err := ExtractBaseDatabase(bundle)
	if err != nil {
		return err
	}

	return writeFileAtomically(outputPath, databaseBytes)
}

func ExtractBaseDatabase(bundle []byte) ([]byte, error) {
	rootArchive, err := zip.NewReader(bytes.NewReader(bundle), int64(len(bundle)))
	if err != nil {
		return nil, fmt.Errorf("open apk bundle: %w", err)
	}

	if databaseBytes, err := readFileFromArchive(rootArchive, kilterAssetPath); err == nil {
		return databaseBytes, nil
	}

	nestedAPK, err := findNestedAPK(rootArchive)
	if err != nil {
		return nil, err
	}

	nestedArchive, err := zip.NewReader(bytes.NewReader(nestedAPK), int64(len(nestedAPK)))
	if err != nil {
		return nil, fmt.Errorf("open nested apk: %w", err)
	}

	databaseBytes, err := readFileFromArchive(nestedArchive, kilterAssetPath)
	if err != nil {
		return nil, err
	}

	return databaseBytes, nil
}

func downloadBundle(ctx context.Context, client *http.Client, url string) ([]byte, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("create bundle request: %w", err)
	}

	request.Header.Set(
		"User-Agent",
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
	)

	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("download base apk bundle: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download base apk bundle: unexpected status %s", response.Status)
	}

	bundle, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read base apk bundle: %w", err)
	}

	return bundle, nil
}

func readFileFromArchive(archive *zip.Reader, path string) ([]byte, error) {
	for _, file := range archive.File {
		if file.Name != path {
			continue
		}

		reader, err := file.Open()
		if err != nil {
			return nil, fmt.Errorf("open %s: %w", path, err)
		}

		defer reader.Close()

		contents, err := io.ReadAll(reader)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}

		return contents, nil
	}

	return nil, fmt.Errorf("%s not found in archive", path)
}

func findNestedAPK(archive *zip.Reader) ([]byte, error) {
	for _, file := range archive.File {
		if !strings.HasSuffix(file.Name, ".apk") {
			continue
		}

		reader, err := file.Open()
		if err != nil {
			return nil, fmt.Errorf("open nested apk %s: %w", file.Name, err)
		}

		defer reader.Close()

		contents, err := io.ReadAll(reader)
		if err != nil {
			return nil, fmt.Errorf("read nested apk %s: %w", file.Name, err)
		}

		return contents, nil
	}

	return nil, errors.New("nested apk not found in bundle")
}

func writeFileAtomically(path string, contents []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return fmt.Errorf("create parent directory: %w", err)
	}

	tempFile, err := os.CreateTemp(filepath.Dir(path), "*.tmp")
	if err != nil {
		return fmt.Errorf("create temp file: %w", err)
	}

	tempPath := tempFile.Name()
	defer os.Remove(tempPath)

	if _, err := tempFile.Write(contents); err != nil {
		tempFile.Close()
		return fmt.Errorf("write temp database: %w", err)
	}

	if err := tempFile.Sync(); err != nil {
		tempFile.Close()
		return fmt.Errorf("sync temp database: %w", err)
	}

	if err := tempFile.Close(); err != nil {
		return fmt.Errorf("close temp database: %w", err)
	}

	if err := os.Rename(tempPath, path); err != nil {
		return fmt.Errorf("replace database file: %w", err)
	}

	return nil
}
