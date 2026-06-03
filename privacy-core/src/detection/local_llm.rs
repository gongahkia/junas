//! Opt-in local LLM classifier for low-confidence OCR regions.
//!
//! This detector is disabled by default. When enabled, it sends only OCR text
//! snippets to a configured localhost model endpoint and converts "secret-shaped"
//! classifications into normal sensitive matches.

use anyhow::{anyhow, bail, Context, Result};
use privacy_common::{
    detection::{SensitiveMatch, Severity, TextRegion},
    frame::Rect,
};
use serde::Deserialize;
use serde_json::json;
use std::time::Duration;

use crate::{config::DetectionConfig, detection::whitelist::Whitelist};

const PATTERN_NAME: &str = "local-llm-secret-shape";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalLlmConfig {
    pub enabled: bool,
    pub provider: String,
    pub endpoint: String,
    pub model: String,
    pub min_confidence: u32,
    pub max_regions_per_frame: usize,
    pub timeout_ms: u64,
}

impl LocalLlmConfig {
    pub fn from_detection_config(config: &DetectionConfig) -> Self {
        Self {
            enabled: config.local_llm_enabled,
            provider: config.local_llm_provider.clone(),
            endpoint: config.local_llm_endpoint.clone(),
            model: config.local_llm_model.clone(),
            min_confidence: config.local_llm_min_confidence.min(100),
            max_regions_per_frame: config.local_llm_max_regions_per_frame,
            timeout_ms: config.local_llm_timeout_ms.max(1),
        }
    }

    pub fn ocr_min_confidence(&self, normal_min_confidence: f32) -> f32 {
        if self.enabled {
            (self.min_confidence as f32).min(normal_min_confidence)
        } else {
            normal_min_confidence
        }
    }

    pub fn should_classify(&self, region: &TextRegion, normal_min_confidence: f32) -> bool {
        self.enabled
            && region.confidence >= self.min_confidence as f32
            && region.confidence < normal_min_confidence
            && !region.text.trim().is_empty()
    }
}

pub struct LocalLlmDetector {
    config: LocalLlmConfig,
    agent: ureq::Agent,
}

impl LocalLlmDetector {
    pub fn new(config: LocalLlmConfig) -> Self {
        let agent = ureq::AgentBuilder::new()
            .timeout(Duration::from_millis(config.timeout_ms))
            .build();
        Self { config, agent }
    }

    pub fn classify_regions(
        &self,
        regions: &[TextRegion],
        whitelist: &Whitelist,
        normal_min_confidence: f32,
    ) -> Vec<SensitiveMatch> {
        classify_low_confidence_regions(
            &self.config,
            regions,
            whitelist,
            normal_min_confidence,
            |text| self.classify_text(text),
        )
    }

    fn classify_text(&self, text: &str) -> Result<bool> {
        match self.config.provider.as_str() {
            "ollama" => self.classify_with_ollama(text),
            other => bail!("unsupported local LLM provider: {other}"),
        }
    }

    fn classify_with_ollama(&self, text: &str) -> Result<bool> {
        let prompt = ollama_prompt(text);
        let payload = json!({
            "model": self.config.model,
            "prompt": prompt,
            "stream": false,
            "options": {
                "temperature": 0,
                "num_predict": 4
            }
        });
        let response = self
            .agent
            .post(&self.config.endpoint)
            .set("Content-Type", "application/json")
            .send_string(&serde_json::to_string(&payload).context("encoding Ollama request JSON")?)
            .with_context(|| format!("calling local Ollama endpoint {}", self.config.endpoint))?;
        let body = response
            .into_string()
            .context("reading local Ollama response body")?;
        let body: OllamaGenerateResponse =
            serde_json::from_str(&body).context("parsing local Ollama response JSON")?;
        parse_secret_classification(&body.response)
    }
}

pub fn classify_low_confidence_regions<F>(
    config: &LocalLlmConfig,
    regions: &[TextRegion],
    whitelist: &Whitelist,
    normal_min_confidence: f32,
    mut classify_text: F,
) -> Vec<SensitiveMatch>
where
    F: FnMut(&str) -> Result<bool>,
{
    if !config.enabled || config.max_regions_per_frame == 0 {
        return Vec::new();
    }

    let mut matches = Vec::new();
    for region in regions
        .iter()
        .filter(|region| config.should_classify(region, normal_min_confidence))
        .take(config.max_regions_per_frame)
    {
        if whitelist.is_safe(&region.text) {
            continue;
        }
        match classify_text(&region.text) {
            Ok(true) => matches.push(local_llm_match(region)),
            Ok(false) => {}
            Err(err) => log::warn!("local LLM classifier skipped region: {err}"),
        }
    }
    matches
}

pub fn parse_secret_classification(response: &str) -> Result<bool> {
    let normalized = response.trim().to_ascii_uppercase();
    if normalized.starts_with("SECRET") {
        return Ok(true);
    }
    if normalized.starts_with("SAFE") {
        return Ok(false);
    }
    Err(anyhow!(
        "local classifier returned neither SECRET nor SAFE: {response:?}"
    ))
}

fn local_llm_match(region: &TextRegion) -> SensitiveMatch {
    SensitiveMatch {
        bounds: Rect {
            x: region.bounds.x,
            y: region.bounds.y,
            width: region.bounds.width,
            height: region.bounds.height,
        },
        pattern_name: PATTERN_NAME.to_string(),
        severity: Severity::Medium,
        snippet: make_snippet(&region.text),
    }
}

fn make_snippet(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    if chars.len() <= 4 {
        return "*".repeat(chars.len());
    }
    let prefix: String = chars[..4].iter().collect();
    format!("{prefix}***")
}

fn ollama_prompt(text: &str) -> String {
    format!(
        "Classify this OCR text from a screen capture as SECRET or SAFE.\n\
         SECRET means it is shaped like an API key, access token, password, private key, JWT, or credential value.\n\
         SAFE means ordinary prose, labels, UI text, file paths, email addresses, or non-credential values.\n\
         Return exactly SECRET or SAFE.\n\
         OCR text: {text:?}"
    )
}

#[derive(Debug, Deserialize)]
struct OllamaGenerateResponse {
    response: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use privacy_common::frame::Rect;

    #[test]
    fn default_config_is_disabled_and_does_not_lower_ocr_threshold() {
        let detection = DetectionConfig::default();
        let config = LocalLlmConfig::from_detection_config(&detection);

        assert!(!config.enabled);
        assert_eq!(config.ocr_min_confidence(40.0), 40.0);
    }

    #[test]
    fn enabled_config_lowers_ocr_threshold_for_low_confidence_regions() {
        let detection = DetectionConfig {
            local_llm_enabled: true,
            local_llm_min_confidence: 15,
            ..DetectionConfig::default()
        };
        let config = LocalLlmConfig::from_detection_config(&detection);

        assert_eq!(config.ocr_min_confidence(40.0), 15.0);
    }

    #[test]
    fn parses_secret_or_safe_classifier_output() {
        assert!(parse_secret_classification("SECRET").unwrap());
        assert!(parse_secret_classification("secret\n").unwrap());
        assert!(!parse_secret_classification("SAFE").unwrap());
        assert!(parse_secret_classification("maybe").is_err());
    }

    #[test]
    fn classifies_only_low_confidence_regions() {
        let config = LocalLlmConfig {
            enabled: true,
            provider: "ollama".to_string(),
            endpoint: "http://127.0.0.1:11434/api/generate".to_string(),
            model: "phi3:mini".to_string(),
            min_confidence: 20,
            max_regions_per_frame: 4,
            timeout_ms: 1,
        };
        let regions = vec![
            text_region("AKIA_LOW_CONFIDENCE", 30.0, 0),
            text_region("HIGH_CONFIDENCE", 80.0, 20),
            text_region("TOO_LOW", 10.0, 40),
        ];

        let matches =
            classify_low_confidence_regions(&config, &regions, &Whitelist::empty(), 60.0, |text| {
                Ok(text.contains("AKIA"))
            });

        assert_eq!(matches.len(), 1);
        assert_eq!(matches[0].pattern_name, PATTERN_NAME);
        assert_eq!(matches[0].bounds.y, 0);
    }

    #[test]
    fn respects_max_regions_per_frame() {
        let config = LocalLlmConfig {
            enabled: true,
            provider: "ollama".to_string(),
            endpoint: "http://127.0.0.1:11434/api/generate".to_string(),
            model: "phi3:mini".to_string(),
            min_confidence: 20,
            max_regions_per_frame: 1,
            timeout_ms: 1,
        };
        let regions = vec![
            text_region("FIRST", 30.0, 0),
            text_region("SECOND", 30.0, 20),
        ];

        let matches =
            classify_low_confidence_regions(&config, &regions, &Whitelist::empty(), 60.0, |_| {
                Ok(true)
            });

        assert_eq!(matches.len(), 1);
        assert_eq!(matches[0].bounds.y, 0);
    }

    fn text_region(text: &str, confidence: f32, y: u32) -> TextRegion {
        TextRegion {
            text: text.to_string(),
            bounds: Rect {
                x: 0,
                y,
                width: 120,
                height: 20,
            },
            confidence,
        }
    }
}
