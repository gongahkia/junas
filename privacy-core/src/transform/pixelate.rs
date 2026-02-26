//! Pixelation transformation: downscale to 1/8 via nearest-neighbor, upscale back.
//! Fastest option (~0.1ms per region).

/// Apply pixelation to a mutable RGBA pixel slice.
pub fn apply_pixelate(pixels: &mut [u8], width: u32, height: u32, intensity: f32) {
    let w = width as usize;
    let h = height as usize;
    // block size scales with intensity: 2px (min) → dim/8 (max)
    let max_block = (w.min(h) / 8).max(2);
    let block = (2.0 + intensity * (max_block as f32 - 2.0)).round() as usize;
    let intensity = intensity.clamp(0.0, 1.0);

    let mut y = 0;
    while y < h {
        let bh = block.min(h - y);
        let mut x = 0;
        while x < w {
            let bw = block.min(w - x);
            // average colour of block
            let (mut r, mut g, mut b, mut a) = (0u32, 0u32, 0u32, 0u32);
            let mut n = 0u32;
            for by in 0..bh {
                for bx in 0..bw {
                    let idx = ((y + by) * w + (x + bx)) * 4;
                    r += pixels[idx] as u32;
                    g += pixels[idx + 1] as u32;
                    b += pixels[idx + 2] as u32;
                    a += pixels[idx + 3] as u32;
                    n += 1;
                }
            }
            let (pr, pg, pb, pa) = (
                (r / n) as u8,
                (g / n) as u8,
                (b / n) as u8,
                (a / n) as u8,
            );
            // fill block with pixelated colour
            for by in 0..bh {
                for bx in 0..bw {
                    let idx = ((y + by) * w + (x + bx)) * 4;
                    pixels[idx] = blend(pixels[idx], pr, intensity);
                    pixels[idx + 1] = blend(pixels[idx + 1], pg, intensity);
                    pixels[idx + 2] = blend(pixels[idx + 2], pb, intensity);
                    pixels[idx + 3] = blend(pixels[idx + 3], pa, intensity);
                }
            }
            x += block;
        }
        y += block;
    }
}

#[inline]
fn blend(orig: u8, px: u8, intensity: f32) -> u8 {
    (orig as f32 * (1.0 - intensity) + px as f32 * intensity).round() as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pixelate_full_intensity_uniform_block() {
        // 8×8 frame all red (255,0,0,255)
        let mut pixels = vec![0u8; 8 * 8 * 4];
        for i in 0..64 {
            pixels[i * 4] = 255;
            pixels[i * 4 + 3] = 255;
        }
        apply_pixelate(&mut pixels, 8, 8, 1.0);
        // all pixels should remain red
        assert_eq!(pixels[0], 255);
        assert_eq!(pixels[1], 0);
    }

    #[test]
    fn zero_intensity_leaves_unchanged() {
        let mut pixels: Vec<u8> = (0..64 * 4).map(|i| i as u8).collect();
        let orig = pixels.clone();
        apply_pixelate(&mut pixels, 8, 8, 0.0);
        assert_eq!(pixels, orig);
    }
}
