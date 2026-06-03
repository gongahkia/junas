use crate::{
    detection::{
        expand::expand_and_merge, line_expand::expand_to_end_of_line, registry::runtime_registry,
        scanner::scan, whitelist::Whitelist,
    },
    transform::registry::apply_transform,
};
use privacy_common::{
    detection::{DetectedRegions, TextRegion},
    frame::{RawFrame, Rect},
    transform::TransformMode,
};
use std::time::Instant;

#[ignore = "synthetic benchmark; run manually with --ignored --nocapture"]
#[test]
fn synthetic_resolution_benchmark() {
    let cases = [
        BenchmarkCase {
            label: "1080p",
            width: 1920,
            height: 1080,
            frames: 120,
        },
        BenchmarkCase {
            label: "1440p",
            width: 2560,
            height: 1440,
            frames: 90,
        },
        BenchmarkCase {
            label: "4k",
            width: 3840,
            height: 2160,
            frames: 45,
        },
    ];
    let registry = runtime_registry(&crate::config::AppConfig::default());
    let whitelist = Whitelist::empty();

    println!("synthetic redaction benchmark: scan + expand + pixelate transform");
    println!("label,resolution,frames,fps,mean_latency_ms,recall");

    for case in cases {
        let frame = fixture_frame(case.width, case.height);
        let regions = fixture_regions(case.width, case.height);
        let expected_patterns = 2usize;
        let started = Instant::now();
        let mut detected_total = 0usize;

        for _ in 0..case.frames {
            let matches = scan(&regions, &registry, &whitelist);
            let merged = expand_to_end_of_line(
                expand_and_merge(matches.clone(), frame.width, frame.height, 0.10),
                frame.width,
            );
            let transformed = apply_transform(
                &frame,
                &DetectedRegions { matches: merged },
                TransformMode::Pixelate,
                1.0,
            )
            .expect("synthetic transform should succeed");
            assert_eq!(transformed.width, frame.width);
            assert_eq!(transformed.height, frame.height);
            detected_total += matches.len().min(expected_patterns);
        }

        let elapsed = started.elapsed().as_secs_f64();
        let fps = case.frames as f64 / elapsed.max(f64::EPSILON);
        let mean_latency_ms = elapsed * 1000.0 / case.frames as f64;
        let recall = detected_total as f64 / (expected_patterns * case.frames as usize) as f64;

        println!(
            "{},{}x{},{},{:.1},{:.2},{:.2}",
            case.label, case.width, case.height, case.frames, fps, mean_latency_ms, recall
        );
    }
}

struct BenchmarkCase {
    label: &'static str,
    width: u32,
    height: u32,
    frames: u32,
}

fn fixture_frame(width: u32, height: u32) -> RawFrame {
    let mut pixels = Vec::with_capacity((width * height * 4) as usize);
    for y in 0..height {
        for x in 0..width {
            pixels.push(((x / 8) % 255) as u8);
            pixels.push(((y / 8) % 255) as u8);
            pixels.push((((x + y) / 16) % 255) as u8);
            pixels.push(255);
        }
    }
    RawFrame {
        pixels,
        width,
        height,
        timestamp: chrono::Utc::now(),
    }
}

fn fixture_regions(width: u32, height: u32) -> Vec<TextRegion> {
    vec![
        TextRegion {
            text: "AKI_FIXTURE_SECRET=DO_NOT_USE_BENCHMARK_VALUE".to_string(),
            bounds: Rect {
                x: width / 16,
                y: height / 10,
                width: width / 3,
                height: (height / 32).max(24),
            },
            confidence: 96.0,
        },
        TextRegion {
            text: "contact: benchmark.user@example.invalid".to_string(),
            bounds: Rect {
                x: width / 16,
                y: height / 5,
                width: width / 4,
                height: (height / 32).max(24),
            },
            confidence: 92.0,
        },
    ]
}
