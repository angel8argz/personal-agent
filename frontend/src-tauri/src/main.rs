// Minimal Tauri shell. No IPC to the Python agent wired up yet — see
// HANDOFF.md's open question on frontend<->agent transport before building
// this out further.

#[tauri::command]
fn ping() -> String {
    "pong".into()
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![ping])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
