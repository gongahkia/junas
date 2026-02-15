mod error;
mod keychain;
mod ml;
mod providers;
mod streaming;
mod tools;
mod types;
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            keychain::get_api_key,
            keychain::set_api_key,
            keychain::delete_api_key,
            providers::chat_claude,
            providers::chat_openai,
            providers::chat_gemini,
            providers::chat_ollama,
            providers::chat_lmstudio,
            tools::fetch_url,
            tools::web_search,
            tools::health_check,
            ml::load_model,
            ml::run_ner,
            ml::run_summarize,
            ml::run_classify,
            ml::run_embeddings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
