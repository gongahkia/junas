//! Frame diff optimization: compute pixel-level diff between consecutive frames,
//! only re-run OCR on regions that changed — potential 50-80% speedup.

use privacy_common::frame::{RawFrame, Rect};

/// Pixel threshold for considering a pixel "changed".
const CHANGE_THRESHOLD: u16 = 20;
/// Minimum changed fraction to mark a grid cell as dirty.
const DIRTY_FRACTION: f32 = 0.03;

/// Track the previous frame and compute a dirty-cell bitmask for incremental OCR.
pub struct FrameDiff {
    prev_pixels: Option<Vec<u8>>,
    pub grid_cols: u32,
    pub grid_rows: u32,
}

impl FrameDiff {
    pub fn new(grid_cols: u32, grid_rows: u32) -> Self {
        Self {
            prev_pixels: None,
            grid_cols,
            grid_rows,
        }
    }

    /// Compare current frame to previous; return list of grid cells that changed.
    /// Returns `None` (all dirty) on first call or if dimensions changed.
    pub fn dirty_cells(&mut self, frame: &RawFrame) -> Option<Vec<(u32, u32)>> {
        let current = &frame.pixels;
        let prev = match &self.prev_pixels {
            Some(p) if p.len() == current.len() => p,
            _ => {
                self.prev_pixels = Some(current.clone());
                return None; // first frame — all dirty
            }
        };

        let w = frame.width as usize;
        let h = frame.height as usize;
        let cell_w = w.div_ceil(self.grid_cols as usize);
        let cell_h = h.div_ceil(self.grid_rows as usize);

        let mut dirty = Vec::new();
        for row in 0..self.grid_rows {
            for col in 0..self.grid_cols {
                let x0 = (col as usize * cell_w).min(w);
                let y0 = (row as usize * cell_h).min(h);
                let x1 = ((col as usize + 1) * cell_w).min(w);
                let y1 = ((row as usize + 1) * cell_h).min(h);
                let total_px = (x1 - x0) * (y1 - y0);
                if total_px == 0 {
                    continue;
                }
                let mut changed = 0usize;
                'outer: for py in y0..y1 {
                    for px in x0..x1 {
                        let idx = (py * w + px) * 4;
                        if idx + 2 >= current.len() {
                            break 'outer;
                        }
                        let dr = (current[idx] as i16 - prev[idx] as i16).unsigned_abs();
                        let dg = (current[idx + 1] as i16 - prev[idx + 1] as i16).unsigned_abs();
                        let db = (current[idx + 2] as i16 - prev[idx + 2] as i16).unsigned_abs();
                        if dr > CHANGE_THRESHOLD || dg > CHANGE_THRESHOLD || db > CHANGE_THRESHOLD {
                            changed += 1;
                        }
                    }
                }
                if changed as f32 / total_px as f32 >= DIRTY_FRACTION {
                    dirty.push((col, row));
                }
            }
        }
        self.prev_pixels = Some(current.clone());
        Some(dirty)
    }

    /// Return the bounding rect of a grid cell.
    pub fn cell_rect(&self, col: u32, row: u32, frame_w: u32, frame_h: u32) -> Rect {
        let cell_w = frame_w.div_ceil(self.grid_cols);
        let cell_h = frame_h.div_ceil(self.grid_rows);
        let x = col * cell_w;
        let y = row * cell_h;
        Rect {
            x,
            y,
            width: cell_w.min(frame_w.saturating_sub(x)),
            height: cell_h.min(frame_h.saturating_sub(y)),
        }
    }
}
