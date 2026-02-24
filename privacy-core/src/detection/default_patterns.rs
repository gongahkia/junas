//! Built-in sensitivity patterns: env vars, secret keywords, known API key prefixes.

use privacy_common::detection::{PatternCategory, Severity};

use super::patterns::{PatternRegistry, SensitivityPattern};

/// Build the default pattern registry with all built-in patterns.
pub fn default_registry() -> PatternRegistry {
    PatternRegistry::new(vec![
        // ── env var assignments: UPPER_CASE=<8+ chars> ──────────────────────────
        SensitivityPattern::new(
            "env_var_assignment",
            r"[A-Z_]{2,}=[^\s]{8,}",
            Severity::Medium,
            PatternCategory::EnvVar,
        ),
        // ── secret keywords ──────────────────────────────────────────────────────
        SensitivityPattern::new(
            "secret_keyword",
            r"(?i)(api[_\-]?key|token|secret|password|passwd|credential)\s*[:=]\s*\S+",
            Severity::High,
            PatternCategory::Password,
        ),
        // ── Stripe secret/publishable keys ──────────────────────────────────────
        SensitivityPattern::new(
            "stripe_key",
            r"(sk|pk)_(?:live|test)_[a-zA-Z0-9]{24,}",
            Severity::High,
            PatternCategory::ApiKey,
        ),
        // ── GitHub personal access tokens ────────────────────────────────────────
        SensitivityPattern::new(
            "github_token",
            r"ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}",
            Severity::High,
            PatternCategory::Token,
        ),
        // ── GitLab personal access tokens ───────────────────────────────────────
        SensitivityPattern::new(
            "gitlab_token",
            r"glpat-[a-zA-Z0-9\-_]{20}",
            Severity::High,
            PatternCategory::Token,
        ),
        // ── Slack tokens (bot, user, workspace) ──────────────────────────────────
        SensitivityPattern::new(
            "slack_token",
            r"xox[bsp]-[a-zA-Z0-9\-]{10,}",
            Severity::High,
            PatternCategory::Token,
        ),
        // ── generic: known API key prefix pattern ────────────────────────────────
        SensitivityPattern::new(
            "generic_api_prefix",
            r"(?i)(sk|pk|ghp|gho|glpat|xox[bsp])-[a-zA-Z0-9]{10,}",
            Severity::High,
            PatternCategory::ApiKey,
        ),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_var_matches() {
        let reg = default_registry();
        let p = reg.patterns.iter().find(|p| p.name == "env_var_assignment").unwrap();
        assert!(p.is_match("DATABASE_URL=postgres://user:pass@host/db"));
        assert!(!p.is_match("PATH=/tmp")); // 4 chars after =, below threshold
    }

    #[test]
    fn secret_keyword_matches() {
        let reg = default_registry();
        let p = reg.patterns.iter().find(|p| p.name == "secret_keyword").unwrap();
        assert!(p.is_match("api_key: abc123xyz"));
        assert!(p.is_match("password=hunter2secret"));
    }

    #[test]
    fn github_token_matches() {
        let reg = default_registry();
        let p = reg.patterns.iter().find(|p| p.name == "github_token").unwrap();
        assert!(p.is_match("ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH12"));
    }
}
