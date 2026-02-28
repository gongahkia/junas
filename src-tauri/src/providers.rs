use crate::error::AppError;
use crate::streaming::stream_sse;
use crate::types::{ChatSettings, Message, ProviderResponse};
use tauri::AppHandle;

const PROVIDER_CONNECT_TIMEOUT_SECS: u64 = 10;
const PROVIDER_REQUEST_TIMEOUT_SECS: u64 = 120;

fn build_client() -> reqwest::Client {
    reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(PROVIDER_CONNECT_TIMEOUT_SECS))
        .timeout(std::time::Duration::from_secs(PROVIDER_REQUEST_TIMEOUT_SECS))
        .build()
        .expect("failed to build http client")
}
// task 20: anthropic/claude
#[tauri::command]
pub async fn chat_claude(app: AppHandle, messages: Vec<Message>, model: String, settings: ChatSettings, api_key: String) -> Result<ProviderResponse, AppError> {
    let client = build_client();
    let mut body = serde_json::json!({
        "model": model,
        "max_tokens": settings.max_tokens.unwrap_or(4096),
        "messages": messages.iter().filter(|m| m.role != "system").map(|m| serde_json::json!({"role": &m.role, "content": &m.content})).collect::<Vec<_>>(),
        "stream": true,
    });
    if let Some(t) = settings.temperature { body["temperature"] = serde_json::json!(t); }
    if let Some(tp) = settings.top_p { body["top_p"] = serde_json::json!(tp); }
    if let Some(ref sp) = settings.system_prompt { body["system"] = serde_json::json!(sp); }
    let resp = client.post("https://api.anthropic.com/v1/messages")
        .header("x-api-key", &api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type", "application/json")
        .json(&body)
        .send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(AppError::Provider(format!("Claude API {status}: {text}")));
    }
    let content = stream_sse(&app, "chat-stream", resp).await?;
    Ok(ProviderResponse { content, model, usage: None })
}
// task 21: openai
#[tauri::command]
pub async fn chat_openai(app: AppHandle, messages: Vec<Message>, model: String, settings: ChatSettings, api_key: String) -> Result<ProviderResponse, AppError> {
    let client = build_client();
    let mut msgs: Vec<serde_json::Value> = vec![];
    if let Some(ref sp) = settings.system_prompt {
        msgs.push(serde_json::json!({"role": "system", "content": sp}));
    }
    for m in &messages { msgs.push(serde_json::json!({"role": &m.role, "content": &m.content})); }
    let mut body = serde_json::json!({ "model": model, "messages": msgs, "stream": true });
    if let Some(t) = settings.temperature { body["temperature"] = serde_json::json!(t); }
    if let Some(mt) = settings.max_tokens { body["max_tokens"] = serde_json::json!(mt); }
    if let Some(tp) = settings.top_p { body["top_p"] = serde_json::json!(tp); }
    let resp = client.post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {api_key}"))
        .json(&body)
        .send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(AppError::Provider(format!("OpenAI API {status}: {text}")));
    }
    let content = stream_sse(&app, "chat-stream", resp).await?;
    Ok(ProviderResponse { content, model, usage: None })
}
// task 22: gemini
#[tauri::command]
pub async fn chat_gemini(app: AppHandle, messages: Vec<Message>, model: String, settings: ChatSettings, api_key: String) -> Result<ProviderResponse, AppError> {
    let client = build_client();
    let contents: Vec<serde_json::Value> = messages.iter().map(|m| {
        let role = if m.role == "assistant" { "model" } else { "user" };
        serde_json::json!({"role": role, "parts": [{"text": &m.content}]})
    }).collect();
    let mut body = serde_json::json!({ "contents": contents });
    if let Some(ref sp) = settings.system_prompt {
        body["systemInstruction"] = serde_json::json!({"parts": [{"text": sp}]});
    }
    let mut gen_config = serde_json::json!({});
    if let Some(t) = settings.temperature { gen_config["temperature"] = serde_json::json!(t); }
    if let Some(mt) = settings.max_tokens { gen_config["maxOutputTokens"] = serde_json::json!(mt); }
    if let Some(tp) = settings.top_p { gen_config["topP"] = serde_json::json!(tp); }
    body["generationConfig"] = gen_config;
    let url = format!("https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}");
    let resp = client.post(&url).json(&body).send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(AppError::Provider(format!("Gemini API {status}: {text}")));
    }
    let content = stream_sse(&app, "chat-stream", resp).await?;
    Ok(ProviderResponse { content, model, usage: None })
}
// task 23: ollama (local)
#[tauri::command]
pub async fn chat_ollama(app: AppHandle, messages: Vec<Message>, model: String, endpoint: String, settings: ChatSettings) -> Result<ProviderResponse, AppError> {
    let client = build_client();
    let mut msgs: Vec<serde_json::Value> = vec![];
    if let Some(ref sp) = settings.system_prompt {
        msgs.push(serde_json::json!({"role": "system", "content": sp}));
    }
    for m in &messages { msgs.push(serde_json::json!({"role": &m.role, "content": &m.content})); }
    let mut body = serde_json::json!({ "model": model, "messages": msgs, "stream": true });
    if let Some(t) = settings.temperature { body["options"] = serde_json::json!({"temperature": t}); }
    let url = format!("{}/api/chat", endpoint.trim_end_matches('/'));
    let resp = client.post(&url).json(&body).send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(AppError::Provider(format!("Ollama {status}: {text}")));
    }
    let content = stream_sse(&app, "chat-stream", resp).await?;
    Ok(ProviderResponse { content, model, usage: None })
}
// task 24: lmstudio (openai-compatible)
#[tauri::command]
pub async fn chat_lmstudio(app: AppHandle, messages: Vec<Message>, model: String, endpoint: String, settings: ChatSettings) -> Result<ProviderResponse, AppError> {
    let client = build_client();
    let mut msgs: Vec<serde_json::Value> = vec![];
    if let Some(ref sp) = settings.system_prompt {
        msgs.push(serde_json::json!({"role": "system", "content": sp}));
    }
    for m in &messages { msgs.push(serde_json::json!({"role": &m.role, "content": &m.content})); }
    let mut body = serde_json::json!({ "model": model, "messages": msgs, "stream": true });
    if let Some(t) = settings.temperature { body["temperature"] = serde_json::json!(t); }
    if let Some(mt) = settings.max_tokens { body["max_tokens"] = serde_json::json!(mt); }
    let url = format!("{}/v1/chat/completions", endpoint.trim_end_matches('/'));
    let resp = client.post(&url).json(&body).send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(AppError::Provider(format!("LMStudio {status}: {text}")));
    }
    let content = stream_sse(&app, "chat-stream", resp).await?;
    Ok(ProviderResponse { content, model, usage: None })
}
