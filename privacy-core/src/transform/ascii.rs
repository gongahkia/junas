//! ASCII-art transformation: map pixel luminance to ASCII density ramp,
//! render characters back as solid-color pixel blocks.

/// ASCII density ramp from dark to light (10 levels).
const RAMP: &[u8] = b" .,:;i1tfLCG08@";
const RAMP_LEN: usize = 15; // len of RAMP

/// Block size in pixels per ASCII "character cell" (e.g., 8×16).
const CHAR_W: usize = 8;
const CHAR_H: usize = 16;

/// Apply ASCII-art effect to a mutable RGBA pixel slice.
/// Each `CHAR_W × CHAR_H` block is averaged to a single luminance,
/// mapped to an ASCII density ramp, and the block pixels are set to
/// a uniform gray matching that density level.
pub fn apply_ascii(pixels: &mut [u8], width: u32, height: u32, intensity: f32) {
    let w = width as usize;
    let h = height as usize;
    let intensity = intensity.clamp(0.0, 1.0);

    let cols = (w + CHAR_W - 1) / CHAR_W;
    let rows = (h + CHAR_H - 1) / CHAR_H;

    for row in 0..rows {
        for col in 0..cols {
            let x0 = col * CHAR_W;
            let y0 = row * CHAR_H;
            let x1 = (x0 + CHAR_W).min(w);
            let y1 = (y0 + CHAR_H).min(h);

            // average luminance over the block
            let (mut lum_sum, mut count) = (0u32, 0u32);
            for y in y0..y1 {
                for x in x0..x1 {
                    let idx = (y * w + x) * 4;
                    let l = (0.299 * pixels[idx] as f32
                        + 0.587 * pixels[idx + 1] as f32
                        + 0.114 * pixels[idx + 2] as f32) as u32;
                    lum_sum += l;
                    count += 1;
                }
            }
            let avg_lum = if count > 0 { lum_sum / count } else { 0 };

            // map luminance → ramp index → grayscale fill value
            let ramp_idx = (avg_lum as usize * (RAMP_LEN - 1) / 255).min(RAMP_LEN - 1);
            let ramp_char = RAMP[ramp_idx];
            // map ramp character (space=32, @=64ish) to a gray level
            let gray = (ramp_char as u32 * 255 / 127).min(255) as u8;

            // fill block with blended gray
            for y in y0..y1 {
                for x in x0..x1 {
                    let idx = (y * w + x) * 4;
                    for c in 0..3 {
                        let orig = pixels[idx + c];
                        pixels[idx + c] = blend(orig, gray, intensity);
                    }
                }
            }
        }
    }
}

#[inline]
fn blend(orig: u8, ascii_px: u8, intensity: f32) -> u8 {
    (orig as f32 * (1.0 - intensity) + ascii_px as f32 * intensity).round() as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ascii_does_not_panic_on_small_frame() {
        let mut pixels = vec![128u8; 4 * 4 * 4]; // 4x4 RGBA
        apply_ascii(&mut pixels, 4, 4, 1.0);
    }

    #[test]
    fn zero_intensity_leaves_pixels_unchanged() {
        let mut pixels: Vec<u8> = (0..16 * 4).map(|i| i as u8).collect();
        let original = pixels.clone();
        apply_ascii(&mut pixels, 4, 4, 0.0);
        assert_eq!(pixels, original);
    }
}
