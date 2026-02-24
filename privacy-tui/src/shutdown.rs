//! Graceful shutdown: stop capture → drain pipeline → flush last frame → close output → exit.

use anyhow::Result;
use privacy_core::pipeline_runner::PipelineHandle;
use privacy_output::OutputSink;

/// Execute ordered shutdown sequence.
/// Called after the TUI event loop exits (q or Ctrl-C).
pub fn ordered_shutdown(
    handle: Option<PipelineHandle>,
    sink: Option<Box<dyn OutputSink>>,
) -> Result<()> {
    // 1. stop capture and drain pipeline threads
    if let Some(h) = handle {
        h.shutdown();
    }
    // 2. flush last frame to output (sink handles buffered writes) and close
    if let Some(mut s) = sink {
        s.close()?;
    }
    Ok(())
}
