//! Cartoon transformation: bilateral filter approximation + Sobel edges + color quantization.
//! Destroys text readability while preserving approximate color vibe.

/// Extract k-means dominant colors (k=8) from an RGBA region.
fn dominant_colors(pixels: &[u8], k: usize) -> Vec<[u8; 3]> {
    if pixels.len() < 4 {
        return vec![[128, 128, 128]];
    }
    // reservoir sample up to 256 pixels for speed
    let count = pixels.len() / 4;
    let step = (count / 256).max(1);
    let samples: Vec<[u8; 3]> = (0..count)
        .step_by(step)
        .map(|i| {
            let b = i * 4;
            [pixels[b], pixels[b + 1], pixels[b + 2]]
        })
        .collect();
    // k-means: initialize centroids as evenly spaced samples
    let k = k.min(samples.len());
    let mut centroids: Vec<[f32; 3]> = (0..k)
        .map(|i| {
            let s = &samples[(i * samples.len() / k).min(samples.len() - 1)];
            [s[0] as f32, s[1] as f32, s[2] as f32]
        })
        .collect();
    for _ in 0..8 {
        // 8 iterations
        let mut sums = vec![[0f32; 3]; k];
        let mut counts = vec![0usize; k];
        for s in &samples {
            let mut best = 0;
            let mut best_d = f32::MAX;
            for (j, c) in centroids.iter().enumerate() {
                let d = (s[0] as f32 - c[0]).powi(2)
                    + (s[1] as f32 - c[1]).powi(2)
                    + (s[2] as f32 - c[2]).powi(2);
                if d < best_d {
                    best_d = d;
                    best = j;
                }
            }
            for c in 0..3 {
                sums[best][c] += s[c] as f32;
            }
            counts[best] += 1;
        }
        for (j, c) in centroids.iter_mut().enumerate() {
            if counts[j] > 0 {
                for ch in 0..3 {
                    c[ch] = sums[j][ch] / counts[j] as f32;
                }
            }
        }
    }
    centroids
        .iter()
        .map(|c| [c[0] as u8, c[1] as u8, c[2] as u8])
        .collect()
}

/// Re-apply a color palette to pixels: map each pixel to its nearest palette color.
fn apply_palette(pixels: &mut [u8], palette: &[[u8; 3]], w: usize, h: usize) {
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            let mut best = 0;
            let mut best_d = u32::MAX;
            for (j, col) in palette.iter().enumerate() {
                let d = (pixels[idx] as i32 - col[0] as i32).pow(2) as u32
                    + (pixels[idx + 1] as i32 - col[1] as i32).pow(2) as u32
                    + (pixels[idx + 2] as i32 - col[2] as i32).pow(2) as u32;
                if d < best_d {
                    best_d = d;
                    best = j;
                }
            }
            pixels[idx] = palette[best][0];
            pixels[idx + 1] = palette[best][1];
            pixels[idx + 2] = palette[best][2];
        }
    }
}

/// Apply cartoon effect to a mutable RGBA pixel slice `(width × height × 4 bytes)`.
/// Extracts dominant colors before transformation and re-applies them afterwards
/// to preserve syntax-highlighting color "vibe".
pub fn apply_cartoon(pixels: &mut [u8], width: u32, height: u32, intensity: f32) {
    let w = width as usize;
    let h = height as usize;

    // extract dominant colors before transformation to preserve palette vibe
    let palette = dominant_colors(pixels, 8);

    // 1. color quantization: snap each channel to 8 levels (0,32,64,...,224)
    let quantized = quantize(pixels, w, h, 8);

    // 2. bilateral filter approximation (weighted Gaussian on 5x5 kernel)
    let smoothed = bilateral_approx(&quantized, w, h);

    // 3. Sobel edge detection → edge mask (0 = interior, 255 = edge)
    let edges = sobel_edges(&smoothed, w, h);

    // 4. composite: interior = smoothed, edges = black; blend by intensity
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            let edge = edges[y * w + x];
            for c in 0..3 {
                let cartoon_px = if edge > 128 { 0u8 } else { smoothed[idx + c] };
                let orig = pixels[idx + c];
                pixels[idx + c] = blend(orig, cartoon_px, intensity);
            }
            // preserve alpha
        }
    }

    // 5. re-apply original color palette to maintain syntax-highlighting vibe
    apply_palette(pixels, &palette, w, h);
}

/// Quantize each RGB channel to `levels` evenly-spaced steps.
fn quantize(pixels: &[u8], w: usize, h: usize, levels: u8) -> Vec<u8> {
    let step = 256u16 / levels as u16;
    let mut out = pixels.to_vec();
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            for c in 0..3 {
                let v = pixels[idx + c] as u16;
                out[idx + c] = ((v / step * step) as u8).min(224);
            }
        }
    }
    out
}

/// Simple bilateral filter approximation: Gaussian weighted average on 5x5 neighborhood,
/// weighted by color similarity (simulates edge-preserving smoothing).
#[allow(clippy::needless_range_loop)]
fn bilateral_approx(pixels: &[u8], w: usize, h: usize) -> Vec<u8> {
    // spatial Gaussian weights for 5x5 (precomputed, sigma=1.5)
    #[rustfmt::skip]
    const KERNEL: [[f32; 5]; 5] = [
        [0.0030, 0.0133, 0.0219, 0.0133, 0.0030],
        [0.0133, 0.0596, 0.0983, 0.0596, 0.0133],
        [0.0219, 0.0983, 0.1621, 0.0983, 0.0219],
        [0.0133, 0.0596, 0.0983, 0.0596, 0.0133],
        [0.0030, 0.0133, 0.0219, 0.0133, 0.0030],
    ];
    const SIGMA_COLOR: f32 = 50.0;

    let mut out = pixels.to_vec();
    for y in 0..h {
        for x in 0..w {
            let cidx = (y * w + x) * 4;
            let mut sum = [0f32; 3];
            let mut wsum = 0f32;
            for ky in 0..5usize {
                for kx in 0..5usize {
                    let ny = y as i32 + ky as i32 - 2;
                    let nx = x as i32 + kx as i32 - 2;
                    if ny < 0 || nx < 0 || ny >= h as i32 || nx >= w as i32 {
                        continue;
                    }
                    let nidx = (ny as usize * w + nx as usize) * 4;
                    // color distance for bilateral weight
                    let color_dist: f32 = (0..3)
                        .map(|c| {
                            let d = pixels[cidx + c] as f32 - pixels[nidx + c] as f32;
                            d * d
                        })
                        .sum::<f32>()
                        .sqrt();
                    let color_w = (-color_dist / (2.0 * SIGMA_COLOR * SIGMA_COLOR)).exp();
                    let w_total = KERNEL[ky][kx] * color_w;
                    for c in 0..3 {
                        sum[c] += pixels[nidx + c] as f32 * w_total;
                    }
                    wsum += w_total;
                }
            }
            if wsum > 0.0 {
                for c in 0..3 {
                    out[cidx + c] = (sum[c] / wsum).clamp(0.0, 255.0) as u8;
                }
            }
        }
    }
    out
}

/// Sobel edge detection: returns single-channel u8 edge intensity per pixel.
fn sobel_edges(pixels: &[u8], w: usize, h: usize) -> Vec<u8> {
    // convert to grayscale luminance, then apply Sobel
    let gray: Vec<f32> = (0..w * h)
        .map(|i| {
            let idx = i * 4;
            0.299 * pixels[idx] as f32
                + 0.587 * pixels[idx + 1] as f32
                + 0.114 * pixels[idx + 2] as f32
        })
        .collect();

    let mut edges = vec![0u8; w * h];
    for y in 1..h - 1 {
        for x in 1..w - 1 {
            let gx = -gray[(y - 1) * w + (x - 1)] + gray[(y - 1) * w + (x + 1)]
                - 2.0 * gray[y * w + (x - 1)]
                + 2.0 * gray[y * w + (x + 1)]
                - gray[(y + 1) * w + (x - 1)]
                + gray[(y + 1) * w + (x + 1)];
            let gy = -gray[(y - 1) * w + (x - 1)]
                - 2.0 * gray[(y - 1) * w + x]
                - gray[(y - 1) * w + (x + 1)]
                + gray[(y + 1) * w + (x - 1)]
                + 2.0 * gray[(y + 1) * w + x]
                + gray[(y + 1) * w + (x + 1)];
            let mag = (gx * gx + gy * gy).sqrt().min(255.0) as u8;
            edges[y * w + x] = mag;
        }
    }
    edges
}

#[inline]
fn blend(orig: u8, transformed: u8, intensity: f32) -> u8 {
    let intensity = intensity.clamp(0.0, 1.0);
    (orig as f32 * (1.0 - intensity) + transformed as f32 * intensity).round() as u8
}
