use crate::error::AppError;
use security_framework::passwords::{get_generic_password, set_generic_password, delete_generic_password};
const SERVICE: &str = "com.gongahkia.junas";
#[tauri::command]
pub fn get_api_key(provider: String) -> Result<String, AppError> {
    let pw = get_generic_password(SERVICE, &provider)
        .map_err(|e| AppError::Keychain(format!("key not found for {provider}: {e}")))?;
    String::from_utf8(pw.to_vec())
        .map_err(|e| AppError::Keychain(format!("invalid utf8: {e}")))
}
#[tauri::command]
pub fn set_api_key(provider: String, key: String) -> Result<(), AppError> {
    set_generic_password(SERVICE, &provider, key.as_bytes())
        .map_err(|e| AppError::Keychain(format!("failed to store key for {provider}: {e}")))
}
#[tauri::command]
pub fn delete_api_key(provider: String) -> Result<(), AppError> {
    delete_generic_password(SERVICE, &provider)
        .map_err(|e| AppError::Keychain(format!("failed to delete key for {provider}: {e}")))
}
