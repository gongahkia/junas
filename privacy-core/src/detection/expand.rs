//! Bounding box expansion (10% padding) and overlapping-region merging.

use privacy_common::{detection::SensitiveMatch, frame::Rect};

/// Expand each match's bounding box by `padding_pct` (0.10 = 10%) on all sides,
/// clamped to `[0, frame_width] × [0, frame_height]`, then merge overlapping boxes.
pub fn expand_and_merge(
    matches: Vec<SensitiveMatch>,
    frame_width: u32,
    frame_height: u32,
    padding_pct: f32,
) -> Vec<SensitiveMatch> {
    if matches.is_empty() {
        return matches;
    }

    // 1. expand each bbox
    let mut expanded: Vec<SensitiveMatch> = matches
        .into_iter()
        .map(|mut m| {
            m.bounds = expand_rect(&m.bounds, frame_width, frame_height, padding_pct);
            m
        })
        .collect();

    // 2. sort by top-left (y then x) for merge sweep
    expanded.sort_by_key(|m| (m.bounds.y, m.bounds.x));

    // 3. greedy merge of overlapping rectangles
    let mut merged: Vec<SensitiveMatch> = Vec::with_capacity(expanded.len());
    for m in expanded {
        if let Some(last) = merged.last_mut() {
            if rects_overlap(&last.bounds, &m.bounds) {
                last.bounds = union_rect(&last.bounds, &m.bounds);
                // keep highest severity (rank(): High=2 > Medium=1 > Low=0)
                if m.severity.rank() > last.severity.rank() {
                    last.severity = m.severity;
                }
                continue;
            }
        }
        merged.push(m);
    }

    merged
}

fn expand_rect(r: &Rect, fw: u32, fh: u32, pct: f32) -> Rect {
    let pad_x = ((r.width as f32 * pct).ceil() as u32).max(1);
    let pad_y = ((r.height as f32 * pct).ceil() as u32).max(1);
    let x = r.x.saturating_sub(pad_x);
    let y = r.y.saturating_sub(pad_y);
    let x2 = (r.x + r.width + pad_x).min(fw);
    let y2 = (r.y + r.height + pad_y).min(fh);
    Rect {
        x,
        y,
        width: x2 - x,
        height: y2 - y,
    }
}

fn rects_overlap(a: &Rect, b: &Rect) -> bool {
    let ax2 = a.x + a.width;
    let ay2 = a.y + a.height;
    let bx2 = b.x + b.width;
    let by2 = b.y + b.height;
    a.x < bx2 && ax2 > b.x && a.y < by2 && ay2 > b.y
}

fn union_rect(a: &Rect, b: &Rect) -> Rect {
    let x = a.x.min(b.x);
    let y = a.y.min(b.y);
    let x2 = (a.x + a.width).max(b.x + b.width);
    let y2 = (a.y + a.height).max(b.y + b.height);
    Rect {
        x,
        y,
        width: x2 - x,
        height: y2 - y,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::detection::Severity;

    fn make_match(x: u32, y: u32, w: u32, h: u32) -> SensitiveMatch {
        SensitiveMatch {
            bounds: Rect {
                x,
                y,
                width: w,
                height: h,
            },
            pattern_name: "test".to_owned(),
            severity: Severity::High,
            snippet: "test***".to_owned(),
        }
    }

    #[test]
    fn non_overlapping_stays_two() {
        let matches = vec![make_match(0, 0, 10, 10), make_match(100, 100, 10, 10)];
        let result = expand_and_merge(matches, 1920, 1080, 0.10);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn overlapping_merges_to_one() {
        let matches = vec![make_match(0, 0, 50, 20), make_match(40, 0, 50, 20)];
        let result = expand_and_merge(matches, 1920, 1080, 0.10);
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn expansion_clamped_to_frame() {
        let matches = vec![make_match(0, 0, 10, 10)];
        let result = expand_and_merge(matches, 100, 100, 0.10);
        assert_eq!(result[0].bounds.x, 0);
        assert_eq!(result[0].bounds.y, 0);
    }
}
