use serde::{Deserialize, Serialize};
use crate::frame::Rect;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PatternCategory {
    EnvVar,
    Token,
    Password,
    ApiKey,
    Pii,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextRegion {
    pub text: String,
    pub bounds: Rect,
    pub confidence: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensitiveMatch {
    pub bounds: Rect,
    pub pattern_name: String,
    pub severity: Severity,
    pub snippet: String, // first 4 chars + "***"
}

#[derive(Debug, Clone, Default)]
pub struct DetectedRegions {
    pub matches: Vec<SensitiveMatch>,
}
