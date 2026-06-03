//! Sensitivity scanner: run all active patterns against OCR TextRegions,
//! return SensitiveMatch list with bounding boxes, pattern name, severity, and snippet.

use privacy_common::detection::{SensitiveMatch, TextRegion};

use super::{patterns::PatternRegistry, whitelist::Whitelist};

/// Run all enabled patterns in `registry` against each `TextRegion`.
/// Regions whose text matches `whitelist` are skipped entirely.
/// Returns a deduplicated list of `SensitiveMatch` entries.
pub fn scan(
    regions: &[TextRegion],
    registry: &PatternRegistry,
    whitelist: &Whitelist,
) -> Vec<SensitiveMatch> {
    let mut matches: Vec<SensitiveMatch> = Vec::new();

    for region in regions {
        if whitelist.is_safe(&region.text) {
            continue;
        }
        for pattern in registry.enabled() {
            if let Some(hit) = pattern.find(&region.text) {
                let snippet = make_snippet(hit);
                // avoid duplicate: same bounding box + pattern
                let already = matches.iter().any(|m| {
                    m.pattern_name == pattern.name
                        && m.bounds.x == region.bounds.x
                        && m.bounds.y == region.bounds.y
                });
                if already {
                    continue;
                }
                matches.push(SensitiveMatch {
                    bounds: region.bounds.clone(),
                    pattern_name: pattern.name.to_owned(),
                    severity: pattern.severity,
                    snippet,
                });
            }
        }
    }

    matches
}

/// Produce a redacted snippet: first 4 chars + "***".
fn make_snippet(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    if chars.len() <= 4 {
        return "*".repeat(chars.len());
    }
    let prefix: String = chars[..4].iter().collect();
    format!("{}***", prefix)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{config::AppConfig, detection::registry::runtime_registry};
    use privacy_common::frame::Rect;
    use serde::Deserialize;

    fn make_region(text: &str) -> TextRegion {
        TextRegion {
            text: text.to_owned(),
            bounds: Rect {
                x: 0,
                y: 0,
                width: 100,
                height: 20,
            },
            confidence: 95.0,
        }
    }

    #[test]
    fn detects_env_var() {
        let reg = runtime_registry(&AppConfig::default());
        let regions = vec![make_region("SECRET_KEY=abc123def456")];
        let matches = scan(
            &regions,
            &reg,
            &crate::detection::whitelist::Whitelist::empty(),
        );
        assert!(!matches.is_empty());
    }

    #[test]
    fn snippet_format() {
        assert_eq!(make_snippet("hello_world"), "hell***");
        assert_eq!(make_snippet("abc"), "***");
    }

    #[test]
    fn synthetic_fixture_corpus_recall_is_tracked() {
        let corpus: FixtureCorpus = toml::from_str(include_str!(
            "../../fixtures/redaction_corpus/synthetic-corpus.toml"
        ))
        .unwrap();
        let registry = runtime_registry(&AppConfig::default());
        let whitelist = crate::detection::whitelist::Whitelist::empty();
        let mut expected = 0usize;
        let mut detected = 0usize;

        for frame in &corpus.frames {
            let regions = frame
                .regions
                .iter()
                .map(|region| TextRegion {
                    text: region.text.clone(),
                    bounds: Rect {
                        x: region.bounds[0],
                        y: region.bounds[1],
                        width: region.bounds[2],
                        height: region.bounds[3],
                    },
                    confidence: region.confidence,
                })
                .collect::<Vec<_>>();
            let matches = scan(&regions, &registry, &whitelist);

            for region in &frame.regions {
                for pattern in &region.expected_patterns {
                    expected += 1;
                    if matches
                        .iter()
                        .any(|candidate| candidate.pattern_name == *pattern)
                    {
                        detected += 1;
                    } else {
                        panic!("{} missed expected pattern {pattern}", frame.id);
                    }
                }
            }
        }

        assert_eq!(expected, 6);
        assert_eq!(detected, expected);
    }

    #[derive(Debug, Deserialize)]
    struct FixtureCorpus {
        frames: Vec<FixtureFrame>,
    }

    #[derive(Debug, Deserialize)]
    struct FixtureFrame {
        id: String,
        regions: Vec<FixtureRegion>,
    }

    #[derive(Debug, Deserialize)]
    struct FixtureRegion {
        text: String,
        bounds: [u32; 4],
        confidence: f32,
        #[serde(default)]
        expected_patterns: Vec<String>,
    }
}
