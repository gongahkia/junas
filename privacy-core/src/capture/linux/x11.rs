#![cfg(target_os = "linux")]

use anyhow::{anyhow, Result};
use chrono::Utc;
use privacy_common::frame::{RawFrame, Rect, WindowInfo};
use xcb::{x, Connection, Xid};

use crate::capture::CaptureSource;

pub struct X11CaptureSource {
    conn: Option<Connection>,
    target_window: Option<x::Window>,
    pub fps: u32,
    pub target: X11CaptureTarget,
}

#[derive(Clone)]
pub enum X11CaptureTarget {
    Window(u64),
    Root,
}

impl X11CaptureSource {
    pub fn new(target: X11CaptureTarget, fps: u32) -> Self {
        Self { conn: None, target_window: None, fps, target }
    }

    fn connect() -> Result<Connection> {
        let (conn, _) = Connection::connect(None)
            .map_err(|e| anyhow!("xcb connect: {}", e))?;
        Ok(conn)
    }

    /// Resolve window by id or use root window.
    fn resolve_window(conn: &Connection, target: &X11CaptureTarget) -> Result<x::Window> {
        let setup = conn.get_setup();
        let screen = setup.roots().next().ok_or_else(|| anyhow!("no X screen"))?;
        match target {
            X11CaptureTarget::Root => Ok(screen.root()),
            X11CaptureTarget::Window(wid) => {
                let win = unsafe { x::Window::new(*wid as u32) };
                Ok(win)
            }
        }
    }

    /// Get window geometry (x, y, w, h).
    fn window_geometry(conn: &Connection, win: x::Window) -> Result<(i16, i16, u16, u16)> {
        let cookie = conn.send_request(&x::GetGeometry {
            drawable: x::Drawable::Window(win),
        });
        let reply = conn.wait_for_reply(cookie)
            .map_err(|e| anyhow!("GetGeometry: {}", e))?;
        Ok((reply.x(), reply.y(), reply.width(), reply.height()))
    }
}

impl CaptureSource for X11CaptureSource {
    fn start(&mut self) -> Result<()> {
        let conn = Self::connect()?;
        let win = Self::resolve_window(&conn, &self.target)?;
        self.target_window = Some(win);
        self.conn = Some(conn);
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        self.conn = None;
        self.target_window = None;
        Ok(())
    }

    fn next_frame(&mut self) -> Result<Option<RawFrame>> {
        let conn = self.conn.as_ref().ok_or_else(|| anyhow!("not started"))?;
        let win = self.target_window.ok_or_else(|| anyhow!("no window"))?;
        let (_, _, w, h) = Self::window_geometry(conn, win)?;

        let cookie = conn.send_request(&x::GetImage {
            format: x::ImageFormat::ZPixmap,
            drawable: x::Drawable::Window(win),
            x: 0,
            y: 0,
            width: w,
            height: h,
            plane_mask: u32::MAX, // all planes
        });
        let reply = conn.wait_for_reply(cookie)
            .map_err(|e| anyhow!("GetImage: {}", e))?;

        let raw = reply.data();
        // X11 ZPixmap is typically BGRA or BGRx (32bpp); convert to RGBA
        let mut rgba = raw.to_vec();
        for chunk in rgba.chunks_exact_mut(4) {
            chunk.swap(0, 2); // B↔R
        }
        Ok(Some(RawFrame {
            pixels: rgba,
            width: w as u32,
            height: h as u32,
            timestamp: Utc::now(),
        }))
    }

    fn list_windows(&self) -> Result<Vec<WindowInfo>> {
        let conn = Self::connect()?;
        let setup = conn.get_setup();
        let screen = setup.roots().next().ok_or_else(|| anyhow!("no X screen"))?;
        let root = screen.root();

        // get _NET_CLIENT_LIST atom
        let atom_cookie = conn.send_request(&x::InternAtom {
            only_if_exists: true,
            name: b"_NET_CLIENT_LIST",
        });
        let atom_reply = conn.wait_for_reply(atom_cookie)
            .map_err(|e| anyhow!("InternAtom: {}", e))?;
        let client_list_atom = atom_reply.atom();

        // get list of client windows from root
        let prop_cookie = conn.send_request(&x::GetProperty {
            delete: false,
            window: root,
            property: client_list_atom,
            r#type: x::ATOM_WINDOW,
            long_offset: 0,
            long_length: 1024,
        });
        let prop = conn.wait_for_reply(prop_cookie)
            .map_err(|e| anyhow!("GetProperty _NET_CLIENT_LIST: {}", e))?;

        // prop value is array of u32 window ids
        let window_ids: &[u32] = prop.value();
        let name_atom = {
            let c = conn.send_request(&x::InternAtom {
                only_if_exists: true,
                name: b"_NET_WM_NAME",
            });
            conn.wait_for_reply(c).map_err(|e| anyhow!("{}", e))?.atom()
        };
        let utf8_atom = {
            let c = conn.send_request(&x::InternAtom {
                only_if_exists: true,
                name: b"UTF8_STRING",
            });
            conn.wait_for_reply(c).map_err(|e| anyhow!("{}", e))?.atom()
        };

        let mut windows = Vec::with_capacity(window_ids.len());
        for &raw_id in window_ids {
            let win = unsafe { x::Window::new(raw_id) };
            // get geometry
            let geo_cookie = conn.send_request(&x::GetGeometry {
                drawable: x::Drawable::Window(win),
            });
            // get title
            let name_cookie = conn.send_request(&x::GetProperty {
                delete: false,
                window: win,
                property: name_atom,
                r#type: utf8_atom,
                long_offset: 0,
                long_length: 256,
            });
            let geo = match conn.wait_for_reply(geo_cookie) {
                Ok(g) => g,
                Err(_) => continue,
            };
            let title = conn.wait_for_reply(name_cookie)
                .map(|r| String::from_utf8_lossy(r.value::<u8>()).into_owned())
                .unwrap_or_default();
            windows.push(WindowInfo {
                id: raw_id as u64,
                title,
                bounds: Rect {
                    x: geo.x() as u32,
                    y: geo.y() as u32,
                    width: geo.width() as u32,
                    height: geo.height() as u32,
                },
            });
        }
        Ok(windows)
    }
}
