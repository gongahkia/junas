//! Incremental OCR: divide frame into grid cells, only re-OCR dirty cells.
//! Uses FrameDiff (pixel-threshold) for dirty-cell detection — ~70% OCR reduction.

use anyhow::Result;
use privacy_common::{detection::TextRegion, frame::RawFrame};

use super::{frame_diff::FrameDiff, ocr::OcrEngine};

/// Default grid dimensions.
pub const GRID_COLS: u32 = 8;
pub const GRID_ROWS: u32 = 6;

/// Cached OCR result for a single grid cell.
#[derive(Clone, Default)]
struct CellCache {
    regions: Vec<TextRegion>,
}

pub struct IncrementalOcr {
    ocr: OcrEngine,
    cols: u32,
    rows: u32,
    cache: Vec<CellCache>, // indexed [row * cols + col]
    diff: FrameDiff,
}

impl IncrementalOcr {
    pub fn new(ocr: OcrEngine, cols: u32, rows: u32) -> Self {
        let n = (cols * rows) as usize;
        Self {
            ocr,
            cols,
            rows,
            cache: vec![CellCache::default(); n],
            diff: FrameDiff::new(cols, rows),
        }
    }

    pub fn with_defaults(ocr: OcrEngine) -> Self {
        Self::new(ocr, GRID_COLS, GRID_ROWS)
    }

    /// Run incremental OCR on a frame; returns flat list of all TextRegions (merged from cells).
    /// Only cells marked dirty by FrameDiff are re-OCR'd.
    pub fn extract(&mut self, frame: &RawFrame) -> Result<Vec<TextRegion>> {
        let fw = frame.width;
        let fh = frame.height;

        // get dirty cells; None means all cells are dirty (first frame or resize)
        let dirty_opt = self.diff.dirty_cells(frame);
        let all_dirty = dirty_opt.is_none();
        let dirty_set: std::collections::HashSet<(u32, u32)> =
            dirty_opt.unwrap_or_default().into_iter().collect();

        let cell_w = (fw + self.cols - 1) / self.cols;
        let cell_h = (fh + self.rows - 1) / self.rows;
        let mut all_regions: Vec<TextRegion> = Vec::new();

        for row in 0..self.rows {
            for col in 0..self.cols {
                let x = col * cell_w;
                let y = row * cell_h;
                let w = cell_w.min(fw.saturating_sub(x));
                let h = cell_h.min(fh.saturating_sub(y));
                if w == 0 || h == 0 {
                    continue;
                }

                let idx = (row * self.cols + col) as usize;

                if !all_dirty && !dirty_set.contains(&(col, row)) {
                    // cell unchanged — reuse cached regions
                    all_regions.extend_from_slice(&self.cache[idx].regions);
                    continue;
                }

                // re-OCR dirty cell
                let cell_frame = extract_sub_frame(frame, x, y, w, h);
                let mut cell_regions = self.ocr.extract(&cell_frame)?;
                for r in &mut cell_regions {
                    r.bounds.x += x;
                    r.bounds.y += y;
                }
                self.cache[idx] = CellCache {
                    regions: cell_regions.clone(),
                };
                all_regions.extend(cell_regions);
            }
        }

        Ok(all_regions)
    }

    /// Invalidate the entire cache (e.g., after resolution change).
    pub fn invalidate(&mut self) {
        for c in &mut self.cache {
            c.regions.clear();
        }
    }

    /// Resize the OCR grid (clamps to min 2×2); invalidates cache.
    pub fn resize_grid(&mut self, cols: u32, rows: u32) {
        let cols = cols.max(2);
        let rows = rows.max(2);
        if self.cols == cols && self.rows == rows {
            return;
        }
        self.cols = cols;
        self.rows = rows;
        self.cache = vec![CellCache::default(); (cols * rows) as usize];
        self.diff = FrameDiff::new(cols, rows);
        log::debug!("adaptive quality: OCR grid resized to {}x{}", cols, rows);
    }

    pub fn cols(&self) -> u32 {
        self.cols
    }
    pub fn rows(&self) -> u32 {
        self.rows
    }
}

/// Extract a rectangular sub-frame (row-major RGBA copy).
fn extract_sub_frame(frame: &RawFrame, x: u32, y: u32, w: u32, h: u32) -> RawFrame {
    let stride = frame.width as usize * 4;
    let row_bytes = w as usize * 4;
    let mut pixels = Vec::with_capacity(h as usize * row_bytes);
    for row in 0..h as usize {
        let start = (y as usize + row) * stride + x as usize * 4;
        pixels.extend_from_slice(&frame.pixels[start..start + row_bytes]);
    }
    RawFrame {
        pixels,
        width: w,
        height: h,
        timestamp: frame.timestamp,
    }
}
