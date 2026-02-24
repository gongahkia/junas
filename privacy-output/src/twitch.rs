//! Twitch IRC integration: display viewer chat in TUI sidebar.
//! Supports `!filter` command to toggle privacy filter on/off.
//! Uses std::net::TcpStream with anonymous IRC (no OAuth for read-only chat).

use anyhow::Result;
use std::{
    io::{BufRead, BufReader, Write},
    net::TcpStream,
    sync::{Arc, Mutex},
    time::Duration,
};

const TWITCH_IRC_HOST: &str = "irc.chat.twitch.tv:6667";
const IRC_NICK: &str = "justinfan12345"; // anonymous read-only
const MAX_MESSAGES: usize = 100;

#[derive(Debug, Clone)]
pub struct TwitchMessage {
    pub username: String,
    pub text: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Shared Twitch IRC client state.
pub struct TwitchClient {
    pub channel: String,
    messages: Arc<Mutex<Vec<TwitchMessage>>>,
    running: Arc<std::sync::atomic::AtomicBool>,
    thread: Option<std::thread::JoinHandle<()>>,
    /// If true, privacy filter is on (controlled via `!filter` chat command).
    pub filter_active: Arc<std::sync::atomic::AtomicBool>,
}

impl TwitchClient {
    pub fn new(channel: impl Into<String>) -> Self {
        Self {
            channel: channel.into(),
            messages: Arc::new(Mutex::new(Vec::new())),
            running: Arc::new(std::sync::atomic::AtomicBool::new(false)),
            thread: None,
            filter_active: Arc::new(std::sync::atomic::AtomicBool::new(true)),
        }
    }

    /// Connect to Twitch IRC and start reading messages in background.
    pub fn connect(&mut self) -> Result<()> {
        let channel = self.channel.trim_start_matches('#').to_lowercase();
        let messages = Arc::clone(&self.messages);
        let running = Arc::clone(&self.running);
        let filter = Arc::clone(&self.filter_active);
        running.store(true, std::sync::atomic::Ordering::SeqCst);

        let thread = std::thread::Builder::new()
            .name("aki-twitch".into())
            .spawn(move || twitch_loop(&channel, messages, running, filter))?;
        self.thread = Some(thread);
        log::info!("Twitch IRC client started for #{}", self.channel);
        Ok(())
    }

    pub fn disconnect(&mut self) {
        self.running.store(false, std::sync::atomic::Ordering::SeqCst);
    }

    /// Take a snapshot of the most recent messages (TUI sidebar).
    pub fn recent_messages(&self, n: usize) -> Vec<TwitchMessage> {
        let guard = self.messages.lock().unwrap();
        guard.iter().rev().take(n).cloned().collect()
    }
}

impl Drop for TwitchClient {
    fn drop(&mut self) { self.disconnect(); }
}

fn twitch_loop(
    channel: &str,
    messages: Arc<Mutex<Vec<TwitchMessage>>>,
    running: Arc<std::sync::atomic::AtomicBool>,
    filter_active: Arc<std::sync::atomic::AtomicBool>,
) {
    let Ok(stream) = TcpStream::connect(TWITCH_IRC_HOST) else {
        log::error!("Twitch IRC: cannot connect to {}", TWITCH_IRC_HOST);
        return;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let mut writer = match stream.try_clone() {
        Ok(s) => s,
        Err(e) => { log::error!("Twitch IRC clone: {e}"); return; }
    };

    // IRC handshake (anonymous)
    let _ = write!(writer, "NICK {}\r\nUSER {} 0 * :aki\r\nJOIN #{}\r\n", IRC_NICK, IRC_NICK, channel);

    let reader = BufReader::new(stream);
    for line in reader.lines() {
        if !running.load(std::sync::atomic::Ordering::Relaxed) { break; }
        let Ok(line) = line else { continue; };
        // Respond to PING keepalive
        if line.starts_with("PING") {
            let pong = line.replace("PING", "PONG");
            let _ = write!(writer, "{}\r\n", pong);
            continue;
        }
        // Parse PRIVMSG
        if let Some(msg) = parse_privmsg(&line) {
            // Handle !filter command
            if msg.text.trim() == "!filter" {
                let prev = filter_active.load(std::sync::atomic::Ordering::Relaxed);
                filter_active.store(!prev, std::sync::atomic::Ordering::Relaxed);
                log::info!("Twitch: {} toggled filter -> {}", msg.username, !prev);
            }
            let mut guard = messages.lock().unwrap();
            guard.push(msg);
            if guard.len() > MAX_MESSAGES { guard.remove(0); }
        }
    }
}

/// Parse a Twitch IRC PRIVMSG line into a TwitchMessage.
fn parse_privmsg(line: &str) -> Option<TwitchMessage> {
    // Format: :username!username@username.tmi.twitch.tv PRIVMSG #channel :message
    if !line.contains("PRIVMSG") { return None; }
    let nick_end = line.find('!')?;
    let username = line[1..nick_end].to_string();
    let msg_start = line.find(" :")?;
    let text = line[msg_start + 2..].to_string();
    Some(TwitchMessage { username, text, timestamp: chrono::Utc::now() })
}
