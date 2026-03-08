package config

import (
	"fmt"
	"log/slog"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var KilterDB *gorm.DB

func ConnectKilterDB(dbPath string) error {
	// Use WAL mode for better concurrency and performance
	dsn := fmt.Sprintf(
		"file:%s?_journal_mode=WAL&"+
			"_synchronous=NORMAL&"+
			"_cache_size=20000&"+ // ~80 MiB cache
			"_mmap_size=157286400&"+ // cap at 150 MiB
			"_temp_store=MEMORY&"+
			"_foreign_keys=ON",
		dbPath,
	)

	var err error
	KilterDB, err = gorm.Open(sqlite.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return fmt.Errorf("connect kilter database: %w", err)
	}
	slog.Info("kilter database connection established")

	// Apply performance indexes
	if err := applyPerformanceIndexes(); err != nil {
		slog.Warn("failed to apply some performance indexes", "error", err)
	}

	return nil
}

func applyPerformanceIndexes() error {
	indexes := []string{
		// Main index for climbs pagination and filtering
		`CREATE INDEX IF NOT EXISTS idx_climbs_pagination 
		 ON climbs(is_listed, created_at DESC, uuid DESC)`,

		// Index for name filtering
		`CREATE INDEX IF NOT EXISTS idx_climbs_name_filter 
		 ON climbs(name, is_listed, created_at DESC)`,

		// Index for layout joins
		`CREATE INDEX IF NOT EXISTS idx_layouts_product 
		 ON layouts(id, product_id)`,

		// Index for product_sizes filtering and joins
		`CREATE INDEX IF NOT EXISTS idx_product_sizes_bounds 
		 ON product_sizes(product_id, edge_left, edge_right, edge_bottom, edge_top, id)`,

		// Index for product_sizes_layouts_sets joins
		`CREATE INDEX IF NOT EXISTS idx_psl_lookup 
		 ON product_sizes_layouts_sets(product_size_id, layout_id, image_filename)`,

		// Index for products listing
		`CREATE INDEX IF NOT EXISTS idx_products_listed 
		 ON products(is_listed, id)`,

		// Index for product_sizes listing and position
		`CREATE INDEX IF NOT EXISTS idx_product_sizes_listing 
		 ON product_sizes(is_listed, position, id, name, product_id)`,

		// Index for climb_stats grade lookups
		`CREATE INDEX IF NOT EXISTS idx_climb_stats_grades 
		 ON climb_stats(climb_uuid, angle, display_difficulty)`,
	}
	for _, indexSQL := range indexes {
		if err := KilterDB.Exec(indexSQL).Error; err != nil {
			slog.Warn("failed to create index", "error", err)
			return err
		}
	}
	return nil
}
