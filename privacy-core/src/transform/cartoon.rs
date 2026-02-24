//! Cartoon transformation: bilateral filter approximation + Sobel edges + color quantization.
//! Destroys text readability while preserving approximate color vibe.

/// Apply cartoon effect to a mutable RGBA pixel slice `(width × height × 4 bytes)`.
pub fn apply_cartoon(pixels: &mut [u8], width: u32, height: u32, intensity: f32) {
    let w = width as usize;
    let h = height as usize;

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
            0.299 * pixels[idx] as f32 + 0.587 * pixels[idx + 1] as f32 + 0.114 * pixels[idx + 2] as f32
        })
        .collect();

    let mut edges = vec![0u8; w * h];
    for y in 1..h - 1 {
        for x in 1..w - 1 {
            let gx = -gray[(y - 1) * w + (x - 1)] + gray[(y - 1) * w + (x + 1)]
                - 2.0 * gray[y * w + (x - 1)] + 2.0 * gray[y * w + (x + 1)]
                - gray[(y + 1) * w + (x - 1)] + gray[(y + 1) * w + (x + 1)];
            let gy = -gray[(y - 1) * w + (x - 1)] - 2.0 * gray[(y - 1) * w + x]
                - gray[(y - 1) * w + (x + 1)] + gray[(y + 1) * w + (x - 1)]
                + 2.0 * gray[(y + 1) * w + x] + gray[(y + 1) * w + (x + 1)];
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
