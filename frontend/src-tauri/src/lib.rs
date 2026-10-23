use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let mut backend_child: Option<Child> = None;

            // En producción, buscar e iniciar el sidecar compilado del backend silenciosamente
            if let Ok(current_exe) = std::env::current_exe() {
                if let Some(exe_dir) = current_exe.parent() {
                    let candidates = [
                        exe_dir.join("bin").join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                        exe_dir.join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                        exe_dir.join("melosync-backend.exe"),
                    ];

                    for cand in &candidates {
                        if cand.exists() {
                            let mut cmd = Command::new(cand);
                            #[cfg(windows)]
                            cmd.creation_flags(CREATE_NO_WINDOW);
                            cmd.stdout(Stdio::null());
                            cmd.stderr(Stdio::null());

                            if let Ok(child) = cmd.spawn() {
                                backend_child = Some(child);
                                break;
                            }
                        }
                    }
                }
            }

            // Forzar la aplicación del icono en la ventana y barra de tareas para Windows/Linux
            if let Some(window) = app.get_webview_window("main") {
                if let Some(icon) = app.default_window_icon() {
                    let _ = window.set_icon(icon.clone());
                }
            }

            app.manage(BackendProcess(Mutex::new(backend_child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut lock) = state.0.lock() {
                        if let Some(child) = lock.take() {
                            #[cfg(windows)]
                            {
                                let pid = child.id();
                                let mut kill_cmd = Command::new("taskkill");
                                kill_cmd.args(["/F", "/T", "/PID", &pid.to_string()]);
                                kill_cmd.creation_flags(CREATE_NO_WINDOW);
                                let _ = kill_cmd.status();
                            }
                            #[cfg(not(windows))]
                            {
                                let _ = child.kill();
                            }
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running meloSync application");
}
