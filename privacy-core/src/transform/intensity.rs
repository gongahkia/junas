//! Transformation intensity control: blend between original and transformed pixels.
//! intensity=1.0 → full transformation, intensity=0.5 → partial overlay, intensity=0.0 → no-op.

/// Blend two RGBA pixel buffers by `intensity` (0.0–1.0).
/// `transformed` is blended into `original` in-place.
pub fn blend_buffers(original: &[u8], transformed: &mut [u8], intensity: f32) {
    let intensity = intensity.clamp(0.0, 1.0);
    let inv = 1.0 - intensity;
    for (o, t) in original.iter().zip(transformed.iter_mut()) {
        *t = (*o as f32 * inv + *t as f32 * intensity).round() as u8;
    }
}

/// Default intensity for all transformations.
pub const DEFAULT_INTENSITY: f32 = 1.0;
/// Minimum allowed intensity (clamped).
pub const MIN_INTENSITY: f32 = 0.0;
/// Maximum allowed intensity (clamped).
pub const MAX_INTENSITY: f32 = 1.0;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_intensity_returns_transformed() {
        let orig = vec![100u8, 150, 200, 255];
        let mut t = vec![0u8, 0, 0, 255];
        blend_buffers(&orig, &mut t, 1.0);
        assert_eq!(t[0], 0);
    }

    #[test]
    fn zero_intensity_returns_original() {
        let orig = vec![100u8, 150, 200, 255];
        let mut t = vec![0u8, 0, 0, 255];
        blend_buffers(&orig, &mut t, 0.0);
        assert_eq!(t[0], 100);
    }

    #[test]
    fn half_intensity_blends() {
        let orig = vec![100u8, 0, 0, 255];
        let mut t = vec![0u8, 0, 0, 255];
        blend_buffers(&orig, &mut t, 0.5);
        assert_eq!(t[0], 50); // (100 * 0.5 + 0 * 0.5) = 50
    }
}
