//! Pattern whitelist: regex patterns for known-safe strings loaded from
//! `~/.config/ascii-privacy/whitelist.toml`. Strings matching any whitelist entry
//! are never flagged as sensitive.
//!
//! File format:
//! ```toml
//! patterns = [
//!     "^PATH=",
//!     "^HOME=",
//!     "^TERM=",
//! ]
//! ```

use anyhow::{Context, Result};
use regex::Regex;
use serde::Deserialize;
use std::path::{Path, PathBuf};

fn config_path() -> PathBuf {
    let base = std::env::var("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".into());
            PathBuf::from(home).join(".config")
        });
    base.join("ascii-privacy/whitelist.toml")
}

#[derive(Deserialize, Default)]
struct WhitelistFile {
    #[serde(default)]
    patterns: Vec<String>,
}

/// Compiled whitelist of safe-string patterns.
#[derive(Clone)]
pub struct Whitelist {
    regexes: Vec<Regex>,
}

impl Whitelist {
    /// Create an empty whitelist (blocks nothing).
    pub fn empty() -> Self {
        Self { regexes: vec![] }
    }
}

impl Whitelist {
    /// Load from the default config path. Returns an empty whitelist if the file is absent.
    pub fn load() -> Result<Self> {
        Self::load_from(config_path())
    }

    pub fn load_from(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        if !path.exists() {
            return Ok(Self { regexes: vec![] });
        }
        let content = std::fs::read_to_string(path)
            .with_context(|| format!("reading whitelist {}", path.display()))?;
        let file: WhitelistFile = toml::from_str(&content)
            .with_context(|| format!("parsing whitelist {}", path.display()))?;
        let regexes = file
            .patterns
            .iter()
            .map(|p| Regex::new(p).with_context(|| format!("invalid whitelist regex: {p}")))
            .collect::<Result<Vec<_>>>()?;
        Ok(Self { regexes })
    }

    /// Returns true if `text` matches any whitelist pattern (i.e., safe — do not redact).
    pub fn is_safe(&self, text: &str) -> bool {
        self.regexes.iter().any(|r| r.is_match(text))
    }

    pub fn is_empty(&self) -> bool {
        self.regexes.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn whitelist_blocks_safe_string() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, r#"patterns = ["^PATH=", "^HOME=", "^TERM="]"#).unwrap();
        let wl = Whitelist::load_from(f.path()).unwrap();
        assert!(wl.is_safe("PATH=/usr/bin:/usr/local/bin"));
        assert!(wl.is_safe("HOME=/Users/alice"));
        assert!(!wl.is_safe("SECRET_KEY=abc123def456"));
    }

    #[test]
    fn missing_file_returns_empty_whitelist() {
        let wl = Whitelist::load_from("/nonexistent/whitelist.toml").unwrap();
        assert!(wl.is_empty());
        assert!(!wl.is_safe("anything")); // empty whitelist blocks nothing
    }
}
