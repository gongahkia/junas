package migrations

import (
	"context"
	"path/filepath"
	"testing"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func expectedSQLMigrationCount(t *testing.T) int {
	t.Helper()

	entries, err := files.ReadDir(".")
	if err != nil {
		t.Fatalf("read embedded migrations: %v", err)
	}

	count := 0
	for _, entry := range entries {
		if !entry.IsDir() && filepath.Ext(entry.Name()) == ".sql" {
			count++
		}
	}
	return count
}

func openTestDB(t *testing.T) *gorm.DB {
	t.Helper()

	dbPath := filepath.Join(t.TempDir(), "app.db")
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite db: %v", err)
	}

	return db
}

func TestApplyFreshDatabase(t *testing.T) {
	db := openTestDB(t)

	if err := Apply(context.Background(), db); err != nil {
		t.Fatalf("apply migrations: %v", err)
	}

	applied, err := ListApplied(context.Background(), db)
	if err != nil {
		t.Fatalf("list applied migrations: %v", err)
	}
	if len(applied) != expectedSQLMigrationCount(t) || applied[0].Version != baselineVersion {
		t.Fatalf("unexpected applied migrations: %#v", applied)
	}
}

func TestApplyAdoptsLegacySchemaBaseline(t *testing.T) {
	db := openTestDB(t)

	sqlBytes, err := files.ReadFile(baselineVersion)
	if err != nil {
		t.Fatalf("read baseline migration: %v", err)
	}
	if err := db.Exec(string(sqlBytes)).Error; err != nil {
		t.Fatalf("seed legacy schema: %v", err)
	}

	if err := Apply(context.Background(), db); err != nil {
		t.Fatalf("apply migrations: %v", err)
	}

	applied, err := ListApplied(context.Background(), db)
	if err != nil {
		t.Fatalf("list applied migrations: %v", err)
	}
	if len(applied) != 1 || applied[0].Version != baselineVersion {
		t.Fatalf("unexpected baseline adoption result: %#v", applied)
	}
}

func TestApplyIsIdempotent(t *testing.T) {
	db := openTestDB(t)

	if err := Apply(context.Background(), db); err != nil {
		t.Fatalf("first apply: %v", err)
	}
	if err := Apply(context.Background(), db); err != nil {
		t.Fatalf("second apply: %v", err)
	}

	applied, err := ListApplied(context.Background(), db)
	if err != nil {
		t.Fatalf("list applied migrations: %v", err)
	}
	if len(applied) != expectedSQLMigrationCount(t) {
		t.Fatalf("expected %d applied migrations after repeated apply, got %#v", expectedSQLMigrationCount(t), applied)
	}
}

func TestApplyMigrationRollsBackOnFailure(t *testing.T) {
	db := openTestDB(t)

	if err := ensureSchemaMigrations(context.Background(), db); err != nil {
		t.Fatalf("ensure schema_migrations: %v", err)
	}
	if err := applyMigration(
		context.Background(),
		db,
		"999_broken.sql",
		"CREATE TABLE sample (id INTEGER PRIMARY KEY);\nTHIS IS NOT VALID SQL;",
	); err == nil {
		t.Fatal("expected broken migration to fail")
	}

	var tableCount int64
	if err := db.Raw(
		`SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'sample'`,
	).Scan(&tableCount).Error; err != nil {
		t.Fatalf("count sample table: %v", err)
	}
	if tableCount != 0 {
		t.Fatalf("expected sample table creation to roll back, got %d", tableCount)
	}

	applied, err := ListApplied(context.Background(), db)
	if err != nil {
		t.Fatalf("list applied migrations: %v", err)
	}
	if len(applied) != 0 {
		t.Fatalf("expected no applied migrations after rollback, got %#v", applied)
	}
}
