//! File-backed logging setup for persistent debugging traces.

use anyhow::{Context, Result};
use simplelog::{
    CombinedLogger, ConfigBuilder, LevelFilter, SharedLogger, SimpleLogger, WriteLogger,
};
use std::{
    fs::{self, OpenOptions},
    path::PathBuf,
};

const DEFAULT_LOG_LEVEL: LevelFilter = LevelFilter::Trace;

/// Initialize logging to both stderr (info+) and a persistent local log file.
pub fn init() -> Result<PathBuf> {
    let log_path = log_dir().join("aki.log");
    if let Some(parent) = log_path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create log directory {}", parent.display()))?;
    }
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .with_context(|| format!("failed to open log file {}", log_path.display()))?;

    let file_level = parse_level(std::env::var("AKI_LOG_LEVEL").ok().as_deref());
    let term_config = ConfigBuilder::new()
        .set_time_level(LevelFilter::Info)
        .set_location_level(LevelFilter::Off)
        .set_target_level(LevelFilter::Off)
        .build();
    let file_config = ConfigBuilder::new()
        .set_time_level(LevelFilter::Trace)
        .set_target_level(LevelFilter::Trace)
        .set_location_level(LevelFilter::Debug)
        .set_thread_level(LevelFilter::Debug)
        .build();

    let mut loggers: Vec<Box<dyn SharedLogger>> = Vec::new();
    if stderr_logging_enabled() {
        loggers.push(SimpleLogger::new(LevelFilter::Info, term_config));
    }
    loggers.push(WriteLogger::new(file_level, file_config, file));
    CombinedLogger::init(loggers).context("failed to initialize combined logger")?;

    log::info!(
        "logging initialized pid={} level={} file={}",
        std::process::id(),
        file_level,
        log_path.display()
    );
    log::trace!("startup args={:?}", std::env::args().collect::<Vec<_>>());
    Ok(log_path)
}

fn stderr_logging_enabled() -> bool {
    matches!(
        std::env::var("AKI_LOG_STDERR")
            .ok()
            .as_deref()
            .map(str::to_ascii_lowercase)
            .as_deref(),
        Some("1") | Some("true") | Some("yes") | Some("on")
    )
}

fn parse_level(value: Option<&str>) -> LevelFilter {
    match value.unwrap_or("").to_ascii_lowercase().as_str() {
        "off" => LevelFilter::Off,
        "error" => LevelFilter::Error,
        "warn" | "warning" => LevelFilter::Warn,
        "info" => LevelFilter::Info,
        "debug" => LevelFilter::Debug,
        "trace" => LevelFilter::Trace,
        _ => DEFAULT_LOG_LEVEL,
    }
}

fn log_dir() -> PathBuf {
    let base = std::env::var("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".config")
        });
    base.join("ascii-privacy").join("logs")
}
