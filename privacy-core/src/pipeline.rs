use crossbeam_channel::{bounded, Receiver, Sender};
use privacy_common::{
    detection::DetectedRegions,
    frame::{RawFrame, TransformedFrame},
};

// channel capacity — backpressure drops oldest frame when full
pub const CHANNEL_CAPACITY: usize = 3;

/// Stage 1 output: raw captured frame
pub type RawFrameSender = Sender<RawFrame>;
pub type RawFrameReceiver = Receiver<RawFrame>;

/// Stage 2 output: frame + detected sensitive regions
pub type DetectionResult = (RawFrame, DetectedRegions);
pub type DetectionSender = Sender<DetectionResult>;
pub type DetectionReceiver = Receiver<DetectionResult>;

/// Stage 3 output: transformed frame ready for output
pub type TransformedSender = Sender<TransformedFrame>;
pub type TransformedReceiver = Receiver<TransformedFrame>;

/// Full pipeline channel set
/// CaptureSource → raw → SensitivityDetector → detected → Transformer → transformed → OutputSink
pub struct PipelineChannels {
    pub raw_tx: RawFrameSender,
    pub raw_rx: RawFrameReceiver,
    pub detection_tx: DetectionSender,
    pub detection_rx: DetectionReceiver,
    pub transformed_tx: TransformedSender,
    pub transformed_rx: TransformedReceiver,
}

impl PipelineChannels {
    pub fn new() -> Self {
        let (raw_tx, raw_rx) = bounded(CHANNEL_CAPACITY);
        let (detection_tx, detection_rx) = bounded(CHANNEL_CAPACITY);
        let (transformed_tx, transformed_rx) = bounded(CHANNEL_CAPACITY);
        Self {
            raw_tx,
            raw_rx,
            detection_tx,
            detection_rx,
            transformed_tx,
            transformed_rx,
        }
    }
}

impl Default for PipelineChannels {
    fn default() -> Self {
        Self::new()
    }
}
