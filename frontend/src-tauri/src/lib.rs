use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let mut backend_child: Option<Child> = None;

            // En producción, buscar e iniciar el sidecar compilado del backend
            if let Ok(current_exe) = std::env::current_exe() {
                if let Some(exe_dir) = current_exe.parent() {
                    let candidates = [
                        exe_dir.join("bin").join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                        exe_dir.join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                        exe_dir.join("melosync-backend.exe"),
                    ];

                    for cand in &candidates {
                        if cand.exists() {
                            if let Ok(child) = Command::new(cand).spawn() {
                                backend_child = Some(child);
                                break;
                            }
                        }
                    }
                }
            }

            app.manage(BackendProcess(Mutex::new(backend_child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut lock) = state.0.lock() {
                        if let Some(mut child) = lock.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running meloSync application");
}
