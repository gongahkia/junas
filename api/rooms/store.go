package rooms

import (
	"context"
	"fmt"

	"github.com/lczm/kilter-together/api/config"
	"gorm.io/gorm"
)

type RoomStore interface {
	WithContext(ctx context.Context) *gorm.DB
}

type GormRoomStore struct {
	DB func() *gorm.DB
}

func NewGormRoomStore(db func() *gorm.DB) *GormRoomStore {
	return &GormRoomStore{DB: db}
}

func (store *GormRoomStore) WithContext(ctx context.Context) *gorm.DB {
	if store == nil || store.DB == nil {
		return nil
	}

	db := store.DB()
	if db == nil {
		return nil
	}

	return db.WithContext(ctx)
}

func defaultRoomStore() RoomStore {
	return NewGormRoomStore(func() *gorm.DB {
		return config.AppDB
	})
}

func mustStoreDB(store RoomStore, ctx context.Context) (*gorm.DB, error) {
	if store == nil {
		return nil, fmt.Errorf("app database is not configured")
	}

	db := store.WithContext(ctx)
	if db == nil {
		return nil, fmt.Errorf("app database is not configured")
	}

	return db, nil
}
