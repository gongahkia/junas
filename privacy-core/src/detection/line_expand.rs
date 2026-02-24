//! Line-level redaction expansion: when a sensitive match is found mid-line,
//! expand the redaction region to cover everything after `=` or `:` to EOL.
//! This prevents partial secret leakage (e.g., showing "SECRET_KEY=abc" without the full value).

use privacy_common::{detection::SensitiveMatch, frame::Rect};

/// For each `SensitiveMatch`, if its region covers only part of the text after a separator,
/// expand the bounding box horizontally to the right edge of the frame (simulating EOL).
///
/// This is an approximation operating at the pixel level:
/// we extend the right edge of the bbox to `frame_width`, keeping y/height unchanged.
pub fn expand_to_end_of_line(
    matches: Vec<SensitiveMatch>,
    frame_width: u32,
) -> Vec<SensitiveMatch> {
    matches
        .into_iter()
        .map(|mut m| {
            // extend right edge to frame boundary (covers remainder of line)
            m.bounds.width = frame_width.saturating_sub(m.bounds.x);
            m
        })
        .collect()
}

/// Text-level expansion: given OCR text for a line and a match position,
/// return the expanded substring from the separator character to end of line.
///
/// Example: `"SECRET_KEY=abc123def"` → match at `KEY=abc` → expanded: `"abc123def"`
pub fn expand_value_after_separator<'a>(line: &'a str, match_text: &'a str) -> &'a str {
    // find where the matched text starts
    let Some(match_start) = line.find(match_text) else {
        return match_text;
    };
    let match_region = &line[match_start..match_start + match_text.len()];
    // find the last `=` or `:` in the matched text
    let sep_offset = match_region.rfind(['=', ':']).map(|i| i + 1).unwrap_or(0);
    let value_start = match_start + sep_offset;
    // return from separator to next whitespace or EOL
    let value = line[value_start..].trim_start(); // skip whitespace after separator
    match value.find(char::is_whitespace) {
        Some(ws) => &value[..ws],
        None => value,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::detection::Severity;

    fn make_match(x: u32, w: u32) -> SensitiveMatch {
        SensitiveMatch {
            bounds: Rect { x, y: 10, width: w, height: 15 },
            pattern_name: "test".to_owned(),
            severity: Severity::High,
            snippet: "test***".to_owned(),
        }
    }

    #[test]
    fn extends_to_frame_right() {
        let matches = vec![make_match(200, 100)];
        let result = expand_to_end_of_line(matches, 1920);
        assert_eq!(result[0].bounds.x, 200);
        assert_eq!(result[0].bounds.width, 1720); // 1920 - 200
    }

    #[test]
    fn value_after_equals() {
        let line = "SECRET_KEY=abc123def ghi";
        let expanded = expand_value_after_separator(line, "KEY=abc123def");
        assert_eq!(expanded, "abc123def");
    }

    #[test]
    fn value_after_colon() {
        let line = "password: hunter2secret extra";
        let expanded = expand_value_after_separator(line, "password: hunter2secret");
        assert_eq!(expanded, "hunter2secret");
    }
}
