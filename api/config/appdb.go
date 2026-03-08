package config

import (
	"fmt"
	"strings"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var AppDB *gorm.DB

func ConnectAppDB(dbPath string) error {
	dsn := fmt.Sprintf(
		"file:%s?_journal_mode=WAL&"+
			"_synchronous=NORMAL&"+
			"_foreign_keys=ON",
		dbPath,
	)

	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		return fmt.Errorf("connect app database: %w", err)
	}

	if err := verifySQLiteIntegrity(db); err != nil {
		return fmt.Errorf("connect app database: %w", err)
	}

	AppDB = db
	return nil
}

func verifySQLiteIntegrity(db *gorm.DB) error {
	sqlDB, err := db.DB()
	if err != nil {
		return fmt.Errorf("open sql db handle: %w", err)
	}

	rows, err := sqlDB.Query("PRAGMA quick_check;")
	if err != nil {
		return fmt.Errorf("run sqlite quick_check: %w", err)
	}
	defer rows.Close()

	issues := make([]string, 0, 4)
	for rows.Next() {
		var result string
		if err := rows.Scan(&result); err != nil {
			return fmt.Errorf("scan sqlite quick_check result: %w", err)
		}
		if strings.TrimSpace(result) == "ok" {
			continue
		}
		issues = append(issues, result)
		if len(issues) >= 4 {
			break
		}
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("read sqlite quick_check rows: %w", err)
	}
	if len(issues) > 0 {
		return fmt.Errorf("sqlite integrity check failed: %s", strings.Join(issues, "; "))
	}

	return nil
}
