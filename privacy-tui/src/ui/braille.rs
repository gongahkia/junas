//! Braille-art rendering for frame previews.
//! Renders RGBA frames as unicode braille characters (2×4 dot patterns, ⠀–⣿)
//! with 256-color approximation, updating at 10 FPS.

use ratatui::{
    layout::Rect,
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

/// Each braille character represents a 2-wide × 4-tall block of pixels.
/// We downsample the frame to fit the pane, then map each 2×4 cell to a braille char.
const BRAILLE_BASE: u32 = 0x2800; // ⠀

/// Dot offsets for braille: standard braille encoding
/// bit 0=dot1(top-left), bit 1=dot2, bit 2=dot3, bit 3=dot7,
/// bit 4=dot4(top-right), bit 5=dot5, bit 6=dot6, bit 7=dot8
const DOT_OFFSETS: [(usize, usize, u32); 8] = [
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (0, 3, 0x40),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (1, 3, 0x80),
];

/// Render a frame as braille art inside `area` with the given block title.
/// `pixels` is RGBA row-major. Call this for both raw and transformed previews.
pub fn render_preview(
    frame: &mut Frame,
    pixels: Option<&[u8]>,
    frame_width: u32,
    frame_height: u32,
    title: &str,
    border_color: Color,
    area: Rect,
) {
    let inner = {
        let block = Block::default()
            .title(format!(" {title} "))
            .borders(Borders::ALL)
            .border_style(Style::default().fg(border_color));
        let inner = block.inner(area);
        frame.render_widget(block, area);
        inner
    };

    if inner.width == 0 || inner.height == 0 {
        return;
    }

    let Some(px) = pixels else {
        // no frame yet — render placeholder
        let placeholder = Paragraph::new("(no signal)");
        frame.render_widget(placeholder, inner);
        return;
    };

    let lines = frame_to_braille_lines(px, frame_width, frame_height, inner.width, inner.height);
    let para = Paragraph::new(lines);
    frame.render_widget(para, inner);
}

/// Convert RGBA pixels to a vec of Ratatui `Line`s using braille characters.
fn frame_to_braille_lines(
    pixels: &[u8],
    fw: u32,
    fh: u32,
    cols: u16, // available terminal columns
    rows: u16, // available terminal rows
) -> Vec<Line<'static>> {
    // Each braille char covers 2 px wide × 4 px tall
    let target_w = cols as u32 * 2;
    let target_h = rows as u32 * 4;

    // scale factors for downsampling
    let scale_x = fw.max(1) as f32 / target_w.max(1) as f32;
    let scale_y = fh.max(1) as f32 / target_h.max(1) as f32;

    let mut lines = Vec::with_capacity(rows as usize);
    for br in 0..rows as u32 {
        let mut spans = Vec::with_capacity(cols as usize);
        for bc in 0..cols as u32 {
            let mut bits = 0u32;
            let mut avg_r = 0u32;
            let mut avg_g = 0u32;
            let mut avg_b = 0u32;
            let mut count = 0u32;

            for (dx, dy, bit) in &DOT_OFFSETS {
                let px_x = ((bc * 2 + *dx as u32) as f32 * scale_x) as u32;
                let px_y = ((br * 4 + *dy as u32) as f32 * scale_y) as u32;
                let px_x = px_x.min(fw.saturating_sub(1));
                let px_y = px_y.min(fh.saturating_sub(1));
                let idx = (px_y * fw + px_x) as usize * 4;
                if idx + 3 < pixels.len() {
                    let lum = (0.299 * pixels[idx] as f32
                        + 0.587 * pixels[idx + 1] as f32
                        + 0.114 * pixels[idx + 2] as f32) as u32;
                    if lum > 96 {
                        bits |= bit;
                    } // threshold
                    avg_r += pixels[idx] as u32;
                    avg_g += pixels[idx + 1] as u32;
                    avg_b += pixels[idx + 2] as u32;
                    count += 1;
                }
            }

            let ch = char::from_u32(BRAILLE_BASE + bits).unwrap_or('⠀');
            let color = if count > 0 {
                color_approx_256(avg_r / count, avg_g / count, avg_b / count)
            } else {
                Color::DarkGray
            };
            spans.push(Span::styled(ch.to_string(), Style::default().fg(color)));
        }
        lines.push(Line::from(spans));
    }
    lines
}

/// Approximate an RGB colour to the nearest terminal 256-colour palette entry.
fn color_approx_256(r: u32, g: u32, b: u32) -> Color {
    // map each channel to 0-5 (6-level cube)
    let ri = ((r * 5 + 127) / 255).min(5) as u8;
    let gi = ((g * 5 + 127) / 255).min(5) as u8;
    let bi = ((b * 5 + 127) / 255).min(5) as u8;
    let idx = 16 + 36 * ri + 6 * gi + bi;
    Color::Indexed(idx)
}
