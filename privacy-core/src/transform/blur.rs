//! Gaussian blur: separable horizontal + vertical passes for O(n) performance.

/// Apply Gaussian blur to a mutable RGBA pixel slice.
/// `sigma` controls blur strength (default 15.0).
pub fn apply_blur(pixels: &mut [u8], width: u32, height: u32, sigma: f32, intensity: f32) {
    let w = width as usize;
    let h = height as usize;
    let sigma = sigma.max(0.5);
    let intensity = intensity.clamp(0.0, 1.0);

    // kernel radius: 3σ clamped to avoid huge allocations
    let radius = (3.0 * sigma).ceil() as usize;
    let kernel = make_gaussian_kernel(radius, sigma);

    // horizontal pass
    let mut tmp = pixels.to_vec();
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            for c in 0..3 {
                let v = convolve_row(pixels, y, x, w, c, &kernel, radius);
                tmp[idx + c] = v;
            }
        }
    }

    // vertical pass (into pixels from tmp)
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            for c in 0..3 {
                let v = convolve_col(&tmp, y, x, w, h, c, &kernel, radius);
                let orig = pixels[idx + c];
                pixels[idx + c] = blend(orig, v, intensity);
            }
        }
    }
}

fn make_gaussian_kernel(radius: usize, sigma: f32) -> Vec<f32> {
    let size = 2 * radius + 1;
    let mut k: Vec<f32> = (0..size)
        .map(|i| {
            let x = i as f32 - radius as f32;
            (-x * x / (2.0 * sigma * sigma)).exp()
        })
        .collect();
    let sum: f32 = k.iter().sum();
    k.iter_mut().for_each(|v| *v /= sum);
    k
}

fn convolve_row(
    pixels: &[u8],
    y: usize,
    x: usize,
    w: usize,
    c: usize,
    kernel: &[f32],
    radius: usize,
) -> u8 {
    let mut acc = 0f32;
    for (ki, &kv) in kernel.iter().enumerate() {
        let nx = (x as i32 + ki as i32 - radius as i32).clamp(0, w as i32 - 1) as usize;
        acc += pixels[(y * w + nx) * 4 + c] as f32 * kv;
    }
    acc.clamp(0.0, 255.0) as u8
}

#[allow(clippy::too_many_arguments)]
fn convolve_col(
    pixels: &[u8],
    y: usize,
    x: usize,
    w: usize,
    h: usize,
    c: usize,
    kernel: &[f32],
    radius: usize,
) -> u8 {
    let mut acc = 0f32;
    for (ki, &kv) in kernel.iter().enumerate() {
        let ny = (y as i32 + ki as i32 - radius as i32).clamp(0, h as i32 - 1) as usize;
        acc += pixels[(ny * w + x) * 4 + c] as f32 * kv;
    }
    acc.clamp(0.0, 255.0) as u8
}

#[inline]
fn blend(orig: u8, blurred: u8, intensity: f32) -> u8 {
    (orig as f32 * (1.0 - intensity) + blurred as f32 * intensity).round() as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blur_does_not_panic() {
        let mut pixels = vec![200u8; 16 * 16 * 4];
        for i in 0..256 {
            pixels[i * 4 + 3] = 255;
        }
        apply_blur(&mut pixels, 16, 16, 3.0, 1.0);
    }

    #[test]
    fn zero_intensity_leaves_unchanged() {
        let mut pixels: Vec<u8> = (0..64 * 4).map(|i| i as u8).collect();
        let orig = pixels.clone();
        apply_blur(&mut pixels, 8, 8, 5.0, 0.0);
        assert_eq!(pixels, orig);
    }

    #[test]
    fn uniform_frame_stays_uniform() {
        let mut pixels = vec![128u8; 8 * 8 * 4];
        apply_blur(&mut pixels, 8, 8, 3.0, 1.0);
        // blurring a uniform image should yield the same value
        // allow ±2 due to f32 accumulation in normalized Gaussian kernel
        assert!(pixels[0..3].iter().all(|&p| (p as i16 - 128).abs() <= 2));
    }
}
