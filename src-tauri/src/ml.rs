use crate::error::AppError;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::AppHandle;
use tauri::Manager;
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
fn models_dir(app: &AppHandle) -> Result<PathBuf, AppError> {
    let dir = app.path().app_data_dir().map_err(|e| AppError::Io(e.to_string()))?.join("models");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}
// task 56: load model (placeholder — actual ONNX loading requires model files)
#[tauri::command]
pub fn load_model(app: AppHandle, model_type: String) -> Result<String, AppError> {
    let dir = models_dir(&app)?;
    let model_path = dir.join(format!("{}.onnx", model_type));
    if !model_path.exists() {
        return Err(AppError::Io(format!("model file not found: {}", model_path.display())));
    }
    Ok(format!("model {} ready at {}", model_type, model_path.display()))
}
// task 57: NER stub
#[tauri::command]
pub fn run_ner(_app: AppHandle, _text: String) -> Result<Vec<NerEntity>, AppError> {
    Err(AppError::Provider("ONNX NER model not yet loaded. Download models from Config > Models.".into()))
}
// task 58: summarize stub
#[tauri::command]
pub fn run_summarize(_app: AppHandle, _text: String, _max_length: u32) -> Result<String, AppError> {
    Err(AppError::Provider("ONNX summarization model not yet loaded. Download models from Config > Models.".into()))
}
// task 59: classify stub
#[tauri::command]
pub fn run_classify(_app: AppHandle, _text: String) -> Result<Vec<ClassifyResult>, AppError> {
    Err(AppError::Provider("ONNX classification model not yet loaded. Download models from Config > Models.".into()))
}
// task 60: embeddings stub
#[tauri::command]
pub fn run_embeddings(_app: AppHandle, _text: String) -> Result<Vec<f32>, AppError> {
    Err(AppError::Provider("ONNX embeddings model not yet loaded. Download models from Config > Models.".into()))
}
