//! macOS system tray indicator using tray-item crate.
//! Shows green/red dot for pipeline status; click to quit.

use anyhow::Result;

/// Spawn the macOS system tray icon in a background thread.
/// `status_rx` receives bool: true = running (green), false = stopped (red).
#[cfg(target_os = "macos")]
pub fn spawn_tray(mut status_rx: std::sync::mpsc::Receiver<bool>) -> Result<()> {
    use tray_item::{IconSource, TrayItem};
    std::thread::Builder::new()
        .name("aki-tray".into())
        .spawn(move || {
            let mut tray = match TrayItem::new("aki", IconSource::Resource("NSStatusAvailable")) {
                Ok(t) => t,
                Err(e) => {
                    log::error!("tray init failed: {e}");
                    return;
                }
            };
            let _ = tray.add_label("aki privacy filter");
            let (quit_tx, quit_rx) = std::sync::mpsc::channel::<()>();
            let _ = tray.add_menu_item("Quit", move || {
                let _ = quit_tx.send(());
            });
            loop {
                // update icon based on pipeline status
                if let Ok(running) = status_rx.try_recv() {
                    let icon = if running {
                        "NSStatusAvailable"
                    } else {
                        "NSStatusUnavailable"
                    };
                    let _ = tray.set_icon(IconSource::Resource(icon));
                }
                if quit_rx.try_recv().is_ok() {
                    std::process::exit(0);
                }
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
        })?;
    Ok(())
}

/// No-op on non-macOS platforms.
#[cfg(not(target_os = "macos"))]
pub fn spawn_tray(_status_rx: std::sync::mpsc::Receiver<bool>) -> Result<()> {
    log::debug!("system tray not supported on this platform");
    Ok(())
}
