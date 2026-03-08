package bootstrap

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"slices"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

const (
	kilterWebBaseURL     = "https://kilterboardapp.com"
	kilterAppUserAgent   = "Kilter%20Board/202 CFNetwork/1568.100.1 Darwin/24.0.0"
	DefaultMaxSyncPages  = 100
	invalidCredentialsSC = http.StatusUnprocessableEntity
)

type kilterLoginEnvelope struct {
	Session struct {
		Token string `json:"token"`
	} `json:"session"`
}

type sharedSyncRow struct {
	TableName          string `json:"table_name"`
	LastSynchronizedAt string `json:"last_synchronized_at"`
}

func Login(ctx context.Context, username, password string) (string, error) {
	payload := map[string]string{
		"username": username,
		"password": password,
		"tou":      "accepted",
		"pp":       "accepted",
		"ua":       "app",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("marshal login payload: %w", err)
	}

	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		kilterWebBaseURL+"/sessions",
		strings.NewReader(string(body)),
	)
	if err != nil {
		return "", fmt.Errorf("create login request: %w", err)
	}

	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Connection", "keep-alive")
	request.Header.Set("Accept-Language", "en-AU,en;q=0.9")
	request.Header.Set("Accept-Encoding", "gzip, deflate, br")
	request.Header.Set("User-Agent", kilterAppUserAgent)

	response, err := defaultHTTPClient.Do(request)
	if err != nil {
		return "", fmt.Errorf("login to kilter: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode == invalidCredentialsSC {
		return "", errors.New("invalid Kilter credentials")
	}
	if response.StatusCode != http.StatusOK {
		return "", fmt.Errorf("login to kilter: unexpected status %s", response.Status)
	}

	var envelope kilterLoginEnvelope
	if err := json.NewDecoder(response.Body).Decode(&envelope); err != nil {
		return "", fmt.Errorf("decode login response: %w", err)
	}
	if strings.TrimSpace(envelope.Session.Token) == "" {
		return "", errors.New("login response missing session token")
	}

	return envelope.Session.Token, nil
}

func SyncSharedData(ctx context.Context, dbPath, token string, maxPages int) error {
	if strings.TrimSpace(token) == "" {
		return errors.New("kilter token is required for shared sync")
	}

	if maxPages <= 0 {
		maxPages = DefaultMaxSyncPages
	}

	sharedSyncs, err := readSharedSyncs(dbPath)
	if err != nil {
		return err
	}

	for page := 0; page < maxPages; page++ {
		rowsByTable, sharedSyncRows, complete, err := syncSharedPage(ctx, token, sharedSyncs)
		if err != nil {
			return err
		}

		if err := applySyncResult(dbPath, rowsByTable); err != nil {
			return err
		}

		for _, row := range sharedSyncRows {
			if _, exists := sharedSyncs[row.TableName]; exists && row.LastSynchronizedAt != "" {
				sharedSyncs[row.TableName] = row.LastSynchronizedAt
			}
		}

		if complete {
			return nil
		}
	}

	return fmt.Errorf("shared sync did not complete after %d pages", maxPages)
}

func syncSharedPage(
	ctx context.Context,
	token string,
	sharedSyncs map[string]string,
) (map[string][]map[string]any, []sharedSyncRow, bool, error) {
	payload := url.Values{}
	for tableName, syncDate := range sharedSyncs {
		payload.Set(tableName, syncDate)
	}

	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		kilterWebBaseURL+"/sync",
		strings.NewReader(payload.Encode()),
	)
	if err != nil {
		return nil, nil, false, fmt.Errorf("create shared sync request: %w", err)
	}

	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", kilterAppUserAgent)
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	request.Header.Set("Cookie", "token="+token)

	response, err := defaultHTTPClient.Do(request)
	if err != nil {
		return nil, nil, false, fmt.Errorf("run shared sync request: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return nil, nil, false, fmt.Errorf("run shared sync request: unexpected status %s", response.Status)
	}

	var rawPayload map[string]json.RawMessage
	if err := json.NewDecoder(response.Body).Decode(&rawPayload); err != nil {
		return nil, nil, false, fmt.Errorf("decode shared sync response: %w", err)
	}

	var complete bool
	if rawValue, exists := rawPayload["_complete"]; exists {
		if err := json.Unmarshal(rawValue, &complete); err != nil {
			return nil, nil, false, fmt.Errorf("decode shared sync completion flag: %w", err)
		}
		delete(rawPayload, "_complete")
	}

	var sharedSyncRows []sharedSyncRow
	if rawValue, exists := rawPayload["shared_syncs"]; exists {
		if err := json.Unmarshal(rawValue, &sharedSyncRows); err != nil {
			return nil, nil, false, fmt.Errorf("decode shared sync rows: %w", err)
		}
	}

	rowsByTable := make(map[string][]map[string]any, len(rawPayload))
	for tableName, rawValue := range rawPayload {
		var rows []map[string]any
		if err := json.Unmarshal(rawValue, &rows); err != nil {
			return nil, nil, false, fmt.Errorf("decode shared sync table %s: %w", tableName, err)
		}
		rowsByTable[tableName] = rows
	}

	return rowsByTable, sharedSyncRows, complete, nil
}

func readSharedSyncs(dbPath string) (map[string]string, error) {
	connection, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("open sqlite database: %w", err)
	}
	defer connection.Close()

	rows, err := connection.Query(`SELECT table_name, last_synchronized_at FROM shared_syncs`)
	if err != nil {
		return nil, fmt.Errorf("query shared syncs: %w", err)
	}
	defer rows.Close()

	sharedSyncs := make(map[string]string)
	for rows.Next() {
		var tableName string
		var syncDate string
		if err := rows.Scan(&tableName, &syncDate); err != nil {
			return nil, fmt.Errorf("scan shared sync row: %w", err)
		}
		sharedSyncs[tableName] = syncDate
	}

	return sharedSyncs, rows.Err()
}

func applySyncResult(dbPath string, rowsByTable map[string][]map[string]any) error {
	connection, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return fmt.Errorf("open sqlite database: %w", err)
	}
	defer connection.Close()

	transaction, err := connection.Begin()
	if err != nil {
		return fmt.Errorf("begin sync transaction: %w", err)
	}

	if err := applySyncRows(transaction, rowsByTable); err != nil {
		transaction.Rollback()
		return err
	}

	if err := transaction.Commit(); err != nil {
		return fmt.Errorf("commit sync transaction: %w", err)
	}

	return nil
}

func applySyncRows(transaction *sql.Tx, rowsByTable map[string][]map[string]any) error {
	for tableName, rows := range rowsByTable {
		if tableName == "climb_stats" {
			if err := applyClimbStatsRows(transaction, rows); err != nil {
				return err
			}
			continue
		}

		if err := applyDefaultRows(transaction, tableName, rows); err != nil {
			return err
		}
	}

	return nil
}

func applyDefaultRows(transaction *sql.Tx, tableName string, rows []map[string]any) error {
	if len(rows) == 0 {
		return nil
	}

	columnNames, err := getTableColumns(transaction, tableName)
	if err != nil {
		return err
	}

	insertSQL := buildInsertSQL(tableName, len(columnNames))
	for _, row := range rows {
		values := rowValues(columnNames, row)
		if _, err := transaction.Exec(insertSQL, values...); err != nil {
			return fmt.Errorf("insert row into %s: %w", tableName, err)
		}
	}

	return nil
}

func applyClimbStatsRows(transaction *sql.Tx, rows []map[string]any) error {
	if len(rows) == 0 {
		return nil
	}

	columnNames, err := getTableColumns(transaction, "climb_stats")
	if err != nil {
		return err
	}

	insertSQL := buildInsertSQL("climb_stats", len(columnNames))
	deleteSQL := `DELETE FROM climb_stats WHERE climb_uuid = ? AND angle = ?`

	for _, row := range rows {
		displayDifficulty := row["benchmark_difficulty"]
		if displayDifficulty == nil {
			displayDifficulty = row["difficulty_average"]
		}

		row["display_difficulty"] = displayDifficulty
		if displayDifficulty == nil {
			if _, err := transaction.Exec(deleteSQL, row["climb_uuid"], row["angle"]); err != nil {
				return fmt.Errorf("delete climb_stats row: %w", err)
			}
			continue
		}

		values := rowValues(columnNames, row)
		if _, err := transaction.Exec(insertSQL, values...); err != nil {
			return fmt.Errorf("insert climb_stats row: %w", err)
		}
	}

	return nil
}

func getTableColumns(transaction *sql.Tx, tableName string) ([]string, error) {
	rows, err := transaction.Query(fmt.Sprintf(`PRAGMA table_info('%s')`, tableName))
	if err != nil {
		return nil, fmt.Errorf("inspect %s columns: %w", tableName, err)
	}
	defer rows.Close()

	var columnNames []string
	for rows.Next() {
		var (
			columnID     int
			columnName   string
			columnType   string
			notNull      int
			defaultValue any
			primaryKey   int
		)
		if err := rows.Scan(
			&columnID,
			&columnName,
			&columnType,
			&notNull,
			&defaultValue,
			&primaryKey,
		); err != nil {
			return nil, fmt.Errorf("scan %s column metadata: %w", tableName, err)
		}

		columnNames = append(columnNames, columnName)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate %s column metadata: %w", tableName, err)
	}

	if len(columnNames) == 0 {
		return nil, fmt.Errorf("no columns found for table %s", tableName)
	}

	return columnNames, nil
}

func buildInsertSQL(tableName string, columnCount int) string {
	return fmt.Sprintf(
		"INSERT OR REPLACE INTO %s VALUES (%s)",
		tableName,
		strings.TrimSuffix(strings.Repeat("?,", columnCount), ","),
	)
}

func rowValues(columnNames []string, row map[string]any) []any {
	values := make([]any, len(columnNames))
	for index, columnName := range columnNames {
		values[index] = normalizeRowValue(row[columnName])
	}

	return values
}

func normalizeRowValue(value any) any {
	switch typedValue := value.(type) {
	case []any:
		return slices.Clone(typedValue)
	default:
		return typedValue
	}
}
