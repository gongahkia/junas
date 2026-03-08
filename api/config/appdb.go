package config

import (
	"fmt"

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

	AppDB = db
	return nil
}
