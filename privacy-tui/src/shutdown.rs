//! Graceful shutdown: stop capture → drain pipeline → flush last frame → close output → exit.

use anyhow::Result;
use privacy_core::pipeline_runner::PipelineHandle;
use privacy_output::OutputSink;
use std::sync::{Arc, Mutex};

/// Execute ordered shutdown sequence.
/// Called after the TUI event loop exits (q or Ctrl-C).
pub fn ordered_shutdown(
    handle: Option<PipelineHandle>,
    sink: Option<Arc<Mutex<Box<dyn OutputSink>>>>,
) -> Result<()> {
    // 1. stop capture and drain pipeline threads
    if let Some(h) = handle {
        h.shutdown();
    }
    // 2. flush last frame to output (sink handles buffered writes) and close
    if let Some(s) = sink {
        if let Ok(mut s) = s.lock() {
            s.close()?;
        }
    }
    Ok(())
}
