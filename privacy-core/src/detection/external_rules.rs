//! Optional imports for established external secret-detection rule packs.

use anyhow::{bail, Context, Result};
use privacy_common::detection::{PatternCategory, Severity};
use serde::Deserialize;
use std::path::Path;

use crate::config::DetectionConfig;

use super::patterns::SensitivityPattern;

pub const DEFAULT_MAX_IMPORTED_PATTERNS: usize = 128;
const MAX_REGEX_BYTES: usize = 4096;

#[derive(Deserialize)]
struct GitleaksFile {
    #[serde(default)]
    rules: Vec<GitleaksRule>,
}

#[derive(Deserialize)]
struct GitleaksRule {
    id: String,
    regex: String,
}

pub fn load_from_config(config: &DetectionConfig) -> Result<Vec<SensitivityPattern>> {
    let path = config.external_rules_path.trim();
    if path.is_empty() {
        return Ok(vec![]);
    }

    let max_patterns = config
        .max_external_patterns
        .min(DEFAULT_MAX_IMPORTED_PATTERNS);
    if max_patterns == 0 {
        return Ok(vec![]);
    }

    match config
        .external_rules_format
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "gitleaks" => load_gitleaks_from_path(Path::new(path), max_patterns),
        other => bail!("unsupported external rule-pack format: {other}"),
    }
}

pub fn load_gitleaks_from_path(
    path: &Path,
    max_patterns: usize,
) -> Result<Vec<SensitivityPattern>> {
    let content =
        std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
    load_gitleaks_from_str(&content, max_patterns)
        .with_context(|| format!("importing gitleaks rules from {}", path.display()))
}

pub fn load_gitleaks_from_str(
    content: &str,
    max_patterns: usize,
) -> Result<Vec<SensitivityPattern>> {
    let file: GitleaksFile = toml::from_str(content).context("parsing gitleaks TOML")?;
    let mut patterns = Vec::new();

    for (idx, rule) in file.rules.into_iter().take(max_patterns).enumerate() {
        if rule.regex.len() > MAX_REGEX_BYTES {
            log::warn!(
                "external rule skipped: gitleaks:{} regex is {} bytes, max is {}",
                rule.id,
                rule.regex.len(),
                MAX_REGEX_BYTES
            );
            continue;
        }

        let id = if rule.id.trim().is_empty() {
            format!("rule-{idx}")
        } else {
            rule.id
        };
        let name = format!("gitleaks:{id}");
        let pattern =
            SensitivityPattern::try_new(name, &rule.regex, Severity::High, PatternCategory::Token)
                .with_context(|| format!("compiling gitleaks rule {id}"))?;
        patterns.push(pattern);
    }

    Ok(patterns)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn imports_gitleaks_fixture_rules() {
        let fixture = include_str!("../../fixtures/gitleaks_rules.toml");
        let patterns = load_gitleaks_from_str(fixture, DEFAULT_MAX_IMPORTED_PATTERNS).unwrap();

        let fixture_token = patterns
            .iter()
            .find(|p| p.name == "gitleaks:fixture-aki-token")
            .unwrap();
        assert!(fixture_token.is_match("token=aki_fixture_ABCDEF123456"));

        let private_key = patterns
            .iter()
            .find(|p| p.name == "gitleaks:fixture-private-key")
            .unwrap();
        assert!(private_key.is_match("-----BEGIN OPENSSH PRIVATE KEY-----"));
    }

    #[test]
    fn caps_imported_gitleaks_rules() {
        let fixture = include_str!("../../fixtures/gitleaks_rules.toml");
        let patterns = load_gitleaks_from_str(fixture, 1).unwrap();
        assert_eq!(patterns.len(), 1);
    }
}
