//! Runtime pattern registry assembly.

use crate::config::AppConfig;

use super::{
    default_patterns::default_registry, external_rules, patterns::PatternRegistry,
    pii_patterns::pii_patterns, user_patterns::load_user_patterns,
};

pub fn runtime_registry(config: &AppConfig) -> PatternRegistry {
    let mut registry = default_registry();
    registry.patterns.extend(pii_patterns());

    match load_user_patterns() {
        Ok(patterns) => registry.patterns.extend(patterns),
        Err(error) => log::warn!("user pattern load failed: {error:#}"),
    }

    match external_rules::load_from_config(&config.detection) {
        Ok(patterns) => {
            if !patterns.is_empty() {
                log::info!("loaded {} external detector patterns", patterns.len());
            }
            registry.patterns.extend(patterns);
        }
        Err(error) => log::warn!("external rule-pack load failed: {error:#}"),
    }

    registry
}
