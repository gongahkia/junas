use crate::error::AppError;
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::AppHandle;
use tauri::Manager;
use tokio::io::AsyncWriteExt;

const MODEL_CONNECT_TIMEOUT_SECS: u64 = 15;
const MODEL_REQUEST_TIMEOUT_SECS: u64 = 300;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NerEntity {
    pub entity: String,
    pub word: String,
    pub start: usize,
    pub end: usize,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClassifyResult {
    pub label: String,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCacheStatus {
    pub model_type: String,
    pub exists: bool,
    pub file_path: String,
    pub size_bytes: u64,
    pub sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ModelCacheMetadata {
    model_type: String,
    source_url: String,
    size_bytes: u64,
    sha256: String,
    downloaded_at_unix: u64,
}

struct ModelAssetSpec {
    model_id: &'static str,
    url: &'static str,
}

fn models_dir(app: &AppHandle) -> Result<PathBuf, AppError> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| AppError::Io(e.to_string()))?
        .join("models");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn model_file_path(app: &AppHandle, model_type: &str) -> Result<PathBuf, AppError> {
    Ok(models_dir(app)?.join(format!("{}.onnx", model_type)))
}

fn metadata_file_path(app: &AppHandle, model_type: &str) -> Result<PathBuf, AppError> {
    Ok(models_dir(app)?.join(format!("{}.json", model_type)))
}

fn model_asset_spec(model_type: &str) -> Result<ModelAssetSpec, AppError> {
    let spec = match model_type {
        "chat" => ModelAssetSpec {
            model_id: "Xenova/distilbart-cnn-6-6",
            url: "https://huggingface.co/Xenova/distilbart-cnn-6-6/resolve/main/onnx/model_quantized.onnx",
        },
        "summarization" => ModelAssetSpec {
            model_id: "Xenova/distilbart-cnn-6-6",
            url: "https://huggingface.co/Xenova/distilbart-cnn-6-6/resolve/main/onnx/model_quantized.onnx",
        },
        "ner" => ModelAssetSpec {
            model_id: "Xenova/bert-base-NER",
            url: "https://huggingface.co/Xenova/bert-base-NER/resolve/main/onnx/model_quantized.onnx",
        },
        "embeddings" => ModelAssetSpec {
            model_id: "Xenova/all-MiniLM-L6-v2",
            url: "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx",
        },
        "text-classification" => ModelAssetSpec {
            model_id: "Xenova/distilbert-base-uncased-finetuned-sst-2-english",
            url: "https://huggingface.co/Xenova/distilbert-base-uncased-finetuned-sst-2-english/resolve/main/onnx/model_quantized.onnx",
        },
        _ => {
            return Err(AppError::Provider(format!(
                "unsupported model type: {model_type}"
            )))
        }
    };
    Ok(spec)
}

fn now_unix_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn compute_sha256(path: &Path) -> Result<String, AppError> {
    let mut file = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 8192];
    loop {
        let bytes_read = file.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        hasher.update(&buffer[..bytes_read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

async fn write_metadata(path: &Path, metadata: &ModelCacheMetadata) -> Result<(), AppError> {
    let serialized = serde_json::to_string_pretty(metadata)?;
    tokio::fs::write(path, serialized)
        .await
        .map_err(|e| AppError::Io(e.to_string()))
}

async fn read_metadata(path: &Path) -> Result<Option<ModelCacheMetadata>, AppError> {
    if !path.exists() {
        return Ok(None);
    }
    let raw = tokio::fs::read_to_string(path)
        .await
        .map_err(|e| AppError::Io(e.to_string()))?;
    let parsed =
        serde_json::from_str::<ModelCacheMetadata>(&raw).map_err(|e| AppError::Parse(e.to_string()))?;
    Ok(Some(parsed))
}

async fn refresh_metadata(app: &AppHandle, model_type: &str, source_url: &str) -> Result<(), AppError> {
    let path = model_file_path(app, model_type)?;
    if !path.exists() {
        return Ok(());
    }
    let size_bytes = std::fs::metadata(&path)?.len();
    let sha256 = compute_sha256(&path)?;
    let metadata = ModelCacheMetadata {
        model_type: model_type.to_string(),
        source_url: source_url.to_string(),
        size_bytes,
        sha256,
        downloaded_at_unix: now_unix_seconds(),
    };
    let metadata_path = metadata_file_path(app, model_type)?;
    write_metadata(&metadata_path, &metadata).await
}

#[tauri::command]
pub async fn download_model(app: AppHandle, model_type: String) -> Result<String, AppError> {
    let spec = model_asset_spec(&model_type)?;
    let target_path = model_file_path(&app, &model_type)?;
    let metadata_path = metadata_file_path(&app, &model_type)?;

    if target_path.exists() {
        refresh_metadata(&app, &model_type, spec.url).await?;
        return Ok(format!(
            "model {model_type} already cached at {}",
            target_path.display()
        ));
    }

    let tmp_path = target_path.with_extension("onnx.download");
    let client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(MODEL_CONNECT_TIMEOUT_SECS))
        .timeout(std::time::Duration::from_secs(MODEL_REQUEST_TIMEOUT_SECS))
        .build()
        .map_err(|e| AppError::Network(e.to_string()))?;
    let response = client.get(spec.url).send().await?;
    if !response.status().is_success() {
        return Err(AppError::Network(format!(
            "model download failed with HTTP {}",
            response.status()
        )));
    }

    let mut stream = response.bytes_stream();
    let mut output_file = tokio::fs::File::create(&tmp_path)
        .await
        .map_err(|e| AppError::Io(e.to_string()))?;
    let mut hasher = Sha256::new();
    let mut total_bytes: u64 = 0;

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(AppError::from)?;
        total_bytes += chunk.len() as u64;
        hasher.update(&chunk);
        output_file
            .write_all(&chunk)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
    }
    output_file
        .flush()
        .await
        .map_err(|e| AppError::Io(e.to_string()))?;
    drop(output_file);

    tokio::fs::rename(&tmp_path, &target_path)
        .await
        .map_err(|e| AppError::Io(e.to_string()))?;

    let metadata = ModelCacheMetadata {
        model_type: model_type.clone(),
        source_url: spec.url.to_string(),
        size_bytes: total_bytes,
        sha256: format!("{:x}", hasher.finalize()),
        downloaded_at_unix: now_unix_seconds(),
    };
    write_metadata(&metadata_path, &metadata).await?;

    Ok(format!(
        "model {model_type} ({}) downloaded to {}",
        spec.model_id,
        target_path.display()
    ))
}

#[tauri::command]
pub async fn get_model_status(app: AppHandle, model_type: String) -> Result<ModelCacheStatus, AppError> {
    let model_path = model_file_path(&app, &model_type)?;
    let metadata_path = metadata_file_path(&app, &model_type)?;
    let exists = model_path.exists();
    let size_bytes = if exists {
        std::fs::metadata(&model_path)?.len()
    } else {
        0
    };
    let metadata = read_metadata(&metadata_path).await?;
    let sha256 = metadata.map(|entry| entry.sha256).or_else(|| {
        if exists {
            compute_sha256(&model_path).ok()
        } else {
            None
        }
    });

    Ok(ModelCacheStatus {
        model_type,
        exists,
        file_path: model_path.display().to_string(),
        size_bytes,
        sha256,
    })
}

#[tauri::command]
pub async fn remove_model_cache(app: AppHandle, model_type: String) -> Result<bool, AppError> {
    let model_path = model_file_path(&app, &model_type)?;
    let metadata_path = metadata_file_path(&app, &model_type)?;
    let mut removed = false;

    if model_path.exists() {
        tokio::fs::remove_file(&model_path)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
        removed = true;
    }

    if metadata_path.exists() {
        tokio::fs::remove_file(&metadata_path)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
        removed = true;
    }

    Ok(removed)
}

#[tauri::command]
pub async fn clear_model_cache(app: AppHandle) -> Result<(), AppError> {
    let dir = models_dir(&app)?;
    if dir.exists() {
        tokio::fs::remove_dir_all(&dir)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
    }
    tokio::fs::create_dir_all(&dir)
        .await
        .map_err(|e| AppError::Io(e.to_string()))
}

#[tauri::command]
pub fn is_onnx_runtime_available() -> bool {
    true
}

#[tauri::command]
pub async fn load_model(app: AppHandle, model_type: String) -> Result<String, AppError> {
    let status = get_model_status(app.clone(), model_type.clone()).await?;
    if !status.exists {
        return Err(AppError::Io(format!(
            "model file not found for {model_type}. Download it from Config > Models."
        )));
    }
    let spec = model_asset_spec(&model_type)?;
    refresh_metadata(&app, &model_type, spec.url).await?;
    Ok(format!(
        "model {model_type} ready at {}",
        status.file_path
    ))
}

// task 57: NER stub
#[tauri::command]
pub fn run_ner(_app: AppHandle, _text: String) -> Result<Vec<NerEntity>, AppError> {
    Err(AppError::Provider(
        "ONNX NER model not yet loaded. Download models from Config > Models.".into(),
    ))
}

// task 58: summarize stub
#[tauri::command]
pub fn run_summarize(_app: AppHandle, _text: String, _max_length: u32) -> Result<String, AppError> {
    Err(AppError::Provider(
        "ONNX summarization model not yet loaded. Download models from Config > Models.".into(),
    ))
}

// task 59: classify stub
#[tauri::command]
pub fn run_classify(_app: AppHandle, _text: String) -> Result<Vec<ClassifyResult>, AppError> {
    Err(AppError::Provider(
        "ONNX classification model not yet loaded. Download models from Config > Models.".into(),
    ))
}

// task 60: embeddings stub
#[tauri::command]
pub fn run_embeddings(_app: AppHandle, _text: String) -> Result<Vec<f32>, AppError> {
    Err(AppError::Provider(
        "ONNX embeddings model not yet loaded. Download models from Config > Models.".into(),
    ))
}
