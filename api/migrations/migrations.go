package migrations

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"gorm.io/gorm"
)

//go:embed *.sql
var files embed.FS

const baselineVersion = "001_initial.sql"

var legacyTables = []string{
	"rooms",
	"room_participants",
	"room_sessions",
	"room_provider_connections",
	"room_queue_entries",
	"room_finalist_entries",
	"provider_cache_entries",
}

type AppliedMigration struct {
	Version   string
	AppliedAt time.Time
}

func Apply(ctx context.Context, db *gorm.DB) error {
	if db == nil {
		return fmt.Errorf("app database is not configured")
	}

	if err := ensureSchemaMigrations(ctx, db); err != nil {
		return err
	}

	applied, err := appliedVersions(ctx, db)
	if err != nil {
		return err
	}

	if len(applied) == 0 {
		existing, err := hasLegacySchema(ctx, db)
		if err != nil {
			return err
		}
		if existing {
			return recordApplied(ctx, db, baselineVersion)
		}

		return bootstrapFreshDatabase(ctx, db)
	}

	versions, err := sqlVersions()
	if err != nil {
		return err
	}

	for _, version := range versions {
		if _, ok := applied[version]; ok {
			continue
		}
		sqlBytes, err := files.ReadFile(version)
		if err != nil {
			return fmt.Errorf("read migration %s: %w", version, err)
		}
		if err := applyMigration(ctx, db, version, string(sqlBytes)); err != nil {
			return err
		}
	}

	return nil
}

func bootstrapFreshDatabase(ctx context.Context, db *gorm.DB) error {
	versions, err := sqlVersions()
	if err != nil {
		return err
	}
	if len(versions) == 0 {
		return nil
	}

	sqlBytes, err := files.ReadFile(baselineVersion)
	if err != nil {
		return fmt.Errorf("read baseline migration %s: %w", baselineVersion, err)
	}
	if err := applyMigration(ctx, db, baselineVersion, string(sqlBytes)); err != nil {
		return err
	}

	for _, version := range versions {
		if version == baselineVersion {
			continue
		}
		if err := recordApplied(ctx, db, version); err != nil {
			return fmt.Errorf("record covered migration %s: %w", version, err)
		}
	}

	return nil
}

func ListApplied(ctx context.Context, db *gorm.DB) ([]AppliedMigration, error) {
	if db == nil {
		return nil, fmt.Errorf("app database is not configured")
	}
	if err := ensureSchemaMigrations(ctx, db); err != nil {
		return nil, err
	}

	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("open sql db handle: %w", err)
	}

	rows, err := sqlDB.QueryContext(ctx, `SELECT version, applied_at FROM schema_migrations ORDER BY version ASC`)
	if err != nil {
		return nil, fmt.Errorf("query schema migrations: %w", err)
	}
	defer rows.Close()

	applied := make([]AppliedMigration, 0)
	for rows.Next() {
		var item AppliedMigration
		if err := rows.Scan(&item.Version, &item.AppliedAt); err != nil {
			return nil, fmt.Errorf("scan schema migration row: %w", err)
		}
		applied = append(applied, item)
	}

	return applied, rows.Err()
}

func ensureSchemaMigrations(ctx context.Context, db *gorm.DB) error {
	return db.WithContext(ctx).Exec(`
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version TEXT PRIMARY KEY,
			applied_at DATETIME NOT NULL
		)
	`).Error
}

func sqlVersions() ([]string, error) {
	entries, err := files.ReadDir(".")
	if err != nil {
		return nil, fmt.Errorf("read embedded migrations: %w", err)
	}

	versions := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sql") {
			continue
		}
		versions = append(versions, entry.Name())
	}
	sort.Strings(versions)
	return versions, nil
}

func appliedVersions(ctx context.Context, db *gorm.DB) (map[string]struct{}, error) {
	rows, err := ListApplied(ctx, db)
	if err != nil {
		return nil, err
	}

	versions := make(map[string]struct{}, len(rows))
	for _, row := range rows {
		versions[row.Version] = struct{}{}
	}
	return versions, nil
}

func recordApplied(ctx context.Context, db *gorm.DB, version string) error {
	return db.WithContext(ctx).Exec(
		`INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)`,
		version,
		time.Now().UTC(),
	).Error
}

func applyMigration(ctx context.Context, db *gorm.DB, version string, sqlText string) error {
	return db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec(sqlText).Error; err != nil {
			return fmt.Errorf("apply migration %s: %w", version, err)
		}
		return tx.Exec(
			`INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)`,
			version,
			time.Now().UTC(),
		).Error
	})
}

func hasLegacySchema(ctx context.Context, db *gorm.DB) (bool, error) {
	sqlDB, err := db.DB()
	if err != nil {
		return false, fmt.Errorf("open sql db handle: %w", err)
	}

	found := 0
	for _, tableName := range legacyTables {
		var exists int
		if err := sqlDB.QueryRowContext(
			ctx,
			`SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?`,
			tableName,
		).Scan(&exists); err != nil {
			return false, fmt.Errorf("inspect %s table: %w", tableName, err)
		}
		if exists > 0 {
			found++
		}
	}

	return found == len(legacyTables), nil
}

func CurrentBaselinePath() string {
	return filepath.Join("api", "migrations", baselineVersion)
}

func SQLDB(db *gorm.DB) (*sql.DB, error) {
	if db == nil {
		return nil, fmt.Errorf("app database is not configured")
	}
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("open sql db handle: %w", err)
	}
	return sqlDB, nil
}
