use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum TransformMode {
    Cartoon,
    Ascii,
    Pixelate,
    #[default]
    Blur,
    Neural, // AnimeGAN v2 neural style transfer
}

impl TransformMode {
    pub fn next(self) -> Self {
        match self {
            Self::Cartoon => Self::Ascii,
            Self::Ascii => Self::Pixelate,
            Self::Pixelate => Self::Blur,
            Self::Blur => Self::Neural,
            Self::Neural => Self::Cartoon,
        }
    }
}
