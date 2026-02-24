//! Sensitivity pattern registry: named regex patterns with severity and category metadata.

use privacy_common::detection::{PatternCategory, Severity};
use regex::Regex;

/// A compiled sensitivity pattern ready for matching.
pub struct SensitivityPattern {
    pub name: &'static str,
    pub regex: Regex,
    pub severity: Severity,
    pub category: PatternCategory,
    pub enabled: bool,
}

impl SensitivityPattern {
    pub fn new(
        name: &'static str,
        pattern: &str,
        severity: Severity,
        category: PatternCategory,
    ) -> Self {
        Self {
            name,
            regex: Regex::new(pattern).expect("invalid sensitivity pattern regex"),
            severity,
            category,
            enabled: true,
        }
    }

    /// Returns true if the pattern matches anywhere in `text`.
    #[inline]
    pub fn is_match(&self, text: &str) -> bool {
        self.enabled && self.regex.is_match(text)
    }

    /// Returns the first matching substring in `text`, if any.
    pub fn find<'t>(&self, text: &'t str) -> Option<&'t str> {
        if !self.enabled {
            return None;
        }
        self.regex.find(text).map(|m| m.as_str())
    }
}

/// Registry holding all active sensitivity patterns.
pub struct PatternRegistry {
    pub patterns: Vec<SensitivityPattern>,
}

impl PatternRegistry {
    pub fn new(patterns: Vec<SensitivityPattern>) -> Self {
        Self { patterns }
    }

    /// Enable/disable a pattern by name.
    pub fn set_enabled(&mut self, name: &str, enabled: bool) {
        for p in &mut self.patterns {
            if p.name == name {
                p.enabled = enabled;
            }
        }
    }

    /// Returns an iterator over enabled patterns.
    pub fn enabled(&self) -> impl Iterator<Item = &SensitivityPattern> {
        self.patterns.iter().filter(|p| p.enabled)
    }

    /// Cycle severity of pattern at index: Low → Medium → High → Low.
    pub fn cycle_severity(&mut self, idx: usize) {
        if let Some(p) = self.patterns.get_mut(idx) {
            p.severity = match p.severity {
                Severity::Low => Severity::Medium,
                Severity::Medium => Severity::High,
                Severity::High => Severity::Low,
            };
        }
    }
}
