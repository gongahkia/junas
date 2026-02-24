//! Event handling: keyboard input + tick events.

use anyhow::Result;
use crossterm::event::{self, Event as CrosstermEvent, KeyCode, KeyEvent, KeyModifiers};
use std::time::Duration;

/// Events dispatched to the main event loop.
#[derive(Debug)]
pub enum Event {
    Key(KeyEvent),
    Tick,
}

/// Poll for the next event, blocking for at most `tick_rate`.
/// Returns `Event::Tick` if the timeout expires with no input.
pub fn next_event(tick_rate: Duration) -> Result<Event> {
    if event::poll(tick_rate)? {
        match event::read()? {
            CrosstermEvent::Key(k) => return Ok(Event::Key(k)),
            _ => {}
        }
    }
    Ok(Event::Tick)
}

/// Returns true if the event is a quit signal (q or Ctrl-C).
pub fn is_quit(ev: &Event) -> bool {
    match ev {
        Event::Key(k) => matches!(
            (k.code, k.modifiers),
            (KeyCode::Char('q'), _) | (KeyCode::Char('c'), KeyModifiers::CONTROL)
        ),
        _ => false,
    }
}
