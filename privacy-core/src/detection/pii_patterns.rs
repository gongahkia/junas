//! PII sensitivity patterns: email, IP, AWS keys, SSH private keys, JWT tokens.

use privacy_common::detection::{PatternCategory, Severity};

use super::patterns::SensitivityPattern;

/// Returns all built-in PII patterns to merge with the default registry.
pub fn pii_patterns() -> Vec<SensitivityPattern> {
    vec![
        // ── email address ────────────────────────────────────────────────────────
        SensitivityPattern::new(
            "email",
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            Severity::Medium,
            PatternCategory::Pii,
        ),
        // ── IPv4 address ─────────────────────────────────────────────────────────
        SensitivityPattern::new(
            "ipv4",
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
            Severity::Low,
            PatternCategory::Pii,
        ),
        // ── IPv6 address (abbreviated) ───────────────────────────────────────────
        SensitivityPattern::new(
            "ipv6",
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|\b::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b",
            Severity::Low,
            PatternCategory::Pii,
        ),
        // ── AWS access key ───────────────────────────────────────────────────────
        SensitivityPattern::new(
            "aws_access_key",
            r"AKIA[0-9A-Z]{16}",
            Severity::High,
            PatternCategory::ApiKey,
        ),
        // ── AWS secret access key (typical 40-char base64 value) ─────────────────
        SensitivityPattern::new(
            "aws_secret_key",
            r#"(?i)aws.{0,20}secret.{0,20}['"][0-9a-zA-Z/+=]{40}['"]"#,
            Severity::High,
            PatternCategory::ApiKey,
        ),
        // ── SSH private key header ───────────────────────────────────────────────
        SensitivityPattern::new(
            "ssh_private_key",
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            Severity::High,
            PatternCategory::Token,
        ),
        // ── JWT token ────────────────────────────────────────────────────────────
        SensitivityPattern::new(
            "jwt_token",
            r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
            Severity::High,
            PatternCategory::Token,
        ),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn find(name: &str) -> SensitivityPattern {
        pii_patterns().into_iter().find(|p| p.name == name).unwrap()
    }

    #[test]
    fn email_matches() {
        let p = find("email");
        assert!(p.is_match("contact: user@example.com"));
        assert!(!p.is_match("not-an-email"));
    }

    #[test]
    fn ipv4_matches() {
        let p = find("ipv4");
        assert!(p.is_match("server: 192.168.1.100"));
        assert!(!p.is_match("version 1.2"));
    }

    #[test]
    fn aws_access_key_matches() {
        let p = find("aws_access_key");
        assert!(p.is_match("AKIAIOSFODNN7EXAMPLE"));
    }

    #[test]
    fn ssh_private_key_matches() {
        let p = find("ssh_private_key");
        assert!(p.is_match("-----BEGIN RSA PRIVATE KEY-----"));
        assert!(p.is_match("-----BEGIN OPENSSH PRIVATE KEY-----"));
    }

    #[test]
    fn jwt_matches() {
        let p = find("jwt_token");
        assert!(p.is_match("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc123"));
    }
}
