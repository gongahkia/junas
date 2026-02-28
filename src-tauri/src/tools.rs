use crate::error::AppError;
use crate::types::SearchResult;
use kuchiki::traits::*;
// task 26: fetch url, sanitize html, return markdown-ish text
#[tauri::command]
pub async fn fetch_url(url: String) -> Result<String, AppError> {
    let client = reqwest::Client::builder().user_agent("Junas/0.1").build().map_err(|e| AppError::Network(e.to_string()))?;
    let resp = client.get(&url).send().await?;
    if !resp.status().is_success() {
        return Err(AppError::Network(format!("HTTP {}", resp.status())));
    }
    let text = resp.text().await?;
    Ok(extract_text_from_html(&text))
}

fn extract_text_from_html(html: &str) -> String {
    let document = kuchiki::parse_html().one(html);

    for selector in ["script", "style", "noscript"] {
        if let Ok(nodes) = document.select(selector) {
            for node in nodes {
                node.as_node().detach();
            }
        }
    }

    normalize_whitespace(&document.text_contents())
}

fn normalize_whitespace(input: &str) -> String {
    input
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
// task 27: web search via serper.dev
#[tauri::command]
pub async fn web_search(query: String, api_key: String) -> Result<Vec<SearchResult>, AppError> {
    let client = reqwest::Client::new();
    let resp = client.post("https://google.serper.dev/search")
        .header("X-API-KEY", &api_key)
        .json(&serde_json::json!({"q": query}))
        .send().await?;
    if !resp.status().is_success() {
        return Err(AppError::Network(format!("Serper API {}", resp.status())));
    }
    let body: serde_json::Value = resp.json().await?;
    let results = body["organic"].as_array()
        .map(|arr| arr.iter().take(10).filter_map(|item| {
            Some(SearchResult {
                title: item["title"].as_str()?.to_string(),
                url: item["link"].as_str()?.to_string(),
                snippet: item["snippet"].as_str().unwrap_or("").to_string(),
            })
        }).collect())
        .unwrap_or_default();
    Ok(results)
}
// task 28: health check
#[tauri::command]
pub async fn health_check(provider: String, endpoint: Option<String>) -> Result<bool, AppError> {
    let client = reqwest::Client::builder().timeout(std::time::Duration::from_secs(5)).build().map_err(|e| AppError::Network(e.to_string()))?;
    let url = match provider.as_str() {
        "claude" => "https://api.anthropic.com/v1/messages".to_string(),
        "openai" => "https://api.openai.com/v1/models".to_string(),
        "gemini" => "https://generativelanguage.googleapis.com/v1beta/models".to_string(),
        "ollama" => format!("{}/api/tags", endpoint.as_deref().unwrap_or("http://localhost:11434")),
        "lmstudio" => format!("{}/v1/models", endpoint.as_deref().unwrap_or("http://localhost:1234")),
        _ => return Err(AppError::Provider(format!("unknown provider: {provider}"))),
    };
    match client.get(&url).send().await {
        Ok(_) => Ok(true),
        Err(_) => Ok(false),
    }
}
