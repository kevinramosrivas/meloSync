use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU16, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{Emitter, Manager};

pub mod windows_identity;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

struct BackendProcess(Mutex<Option<Child>>);
struct BackendPort(Arc<AtomicU16>);

// Global reference to child PID so console CTRL_C / CTRL_CLOSE handlers can terminate it immediately
static CHILD_BACKEND_PID: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);

#[cfg(windows)]
unsafe extern "system" fn console_ctrl_handler(_ctrl_type: u32) -> i32 {
    let pid = CHILD_BACKEND_PID.swap(0, Ordering::SeqCst);
    if pid > 0 {
        let mut kill_cmd = Command::new("taskkill");
        kill_cmd.args(["/F", "/T", "/PID", &pid.to_string()]);
        kill_cmd.creation_flags(CREATE_NO_WINDOW);
        let _ = kill_cmd.status();
    }
    // Return 0 to let the next handler/OS finish default Ctrl+C processing
    0
}

#[cfg(windows)]
fn enable_kill_on_job_close(child: &Child) {
    use std::os::windows::io::AsRawHandle;

    #[repr(C)]
    struct IoCounters {
        read_operation_count: u64,
        write_operation_count: u64,
        other_operation_count: u64,
        read_transfer_count: u64,
        write_transfer_count: u64,
        other_transfer_count: u64,
    }

    #[repr(C)]
    struct JobobjectBasicLimitInformation {
        per_process_user_time_limit: i64,
        per_job_user_time_limit: i64,
        limit_flags: u32,
        minimum_working_set_size: usize,
        maximum_working_set_size: usize,
        active_process_limit: u32,
        affinity: usize,
        priority_class: u32,
        scheduling_class: u32,
    }

    #[repr(C)]
    struct JobobjectExtendedLimitInformation {
        basic_limit_information: JobobjectBasicLimitInformation,
        io_info: IoCounters,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory_limit: usize,
        peak_job_memory_limit: usize,
    }

    extern "system" {
        fn CreateJobObjectW(
            lp_job_attributes: *mut std::ffi::c_void,
            lp_name: *const u16,
        ) -> *mut std::ffi::c_void;
        fn SetInformationJobObject(
            h_job: *mut std::ffi::c_void,
            job_object_info_class: i32,
            lp_job_object_info: *const std::ffi::c_void,
            cb_job_object_info_length: u32,
        ) -> i32;
        fn AssignProcessToJobObject(
            h_job: *mut std::ffi::c_void,
            h_process: *mut std::ffi::c_void,
        ) -> i32;
    }

    unsafe {
        let job = CreateJobObjectW(std::ptr::null_mut(), std::ptr::null());
        if !job.is_null() {
            let mut info: JobobjectExtendedLimitInformation = std::mem::zeroed();
            const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: u32 = 0x2000;
            info.basic_limit_information.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                job,
                9, // JobObjectExtendedLimitInformation
                &info as *const _ as *const std::ffi::c_void,
                std::mem::size_of::<JobobjectExtendedLimitInformation>() as u32,
            ) != 0
            {
                let process_handle = child.as_raw_handle() as *mut std::ffi::c_void;
                let _ = AssignProcessToJobObject(job, process_handle);
                // Mantenemos el job abierto durante la vida de este proceso;
                // en cuanto melosync.exe se cierre (o muera con Ctrl+C/crash), Windows cierra el handle y mata el subproceso.
                let _ = job;
            }
        }
    }
}

/// Verifica mediante HTTP GET /health (con timeout estricto) si el servicio en `port` es meloSync API.
fn is_melosync_healthy(port: u16) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    if let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(150)) {
        let _ = stream.set_read_timeout(Some(Duration::from_millis(250)));
        let _ = stream.set_write_timeout(Some(Duration::from_millis(200)));
        let req = format!(
            "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
            port
        );
        if stream.write_all(req.as_bytes()).is_ok() {
            let mut buf = [0u8; 512];
            if let Ok(n) = stream.read(&mut buf) {
                let resp = String::from_utf8_lossy(&buf[..n]);
                return resp.contains("meloSync API");
            }
        }
    }
    false
}

/// Lee el archivo ~/.melosync/active_port.json escrito por run.py si existe.
fn read_discovery_port() -> Option<u16> {
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .ok()?;
    let path = PathBuf::from(home).join(".melosync").join("active_port.json");
    let content = std::fs::read_to_string(path).ok()?;
    let idx = content.find("\"port\"")?;
    let rest = &content[idx + 6..];
    let digits: String = rest
        .chars()
        .skip_while(|c| !c.is_ascii_digit())
        .take_while(|c| c.is_ascii_digit())
        .collect();
    let port: u16 = digits.parse().ok()?;
    if port > 0 {
        Some(port)
    } else {
        None
    }
}

/// Resuelve el puerto para el backend: devuelve `(puerto, ya_estaba_corriendo)`.
fn resolve_backend_port() -> (u16, bool) {
    // 1. Si meloSync ya está respondiendo en el puerto estándar 8000, reutilizarlo
    if is_melosync_healthy(8000) {
        return (8000, true);
    }

    // 2. Si meloSync ya fue iniciado externamente (ej. dev.bat) en un puerto efímero y responde /health, reutilizarlo
    if let Some(disc_port) = read_discovery_port() {
        if disc_port != 8000 && is_melosync_healthy(disc_port) {
            return (disc_port, true);
        }
    }

    // 3. Si el puerto estándar 8000 está libre para ser enlazado, usarlo
    if let Ok(listener) = TcpListener::bind("127.0.0.1:8000") {
        drop(listener);
        return (8000, false);
    }

    // 4. El puerto 8000 está ocupado por OTRA aplicación externa: solicitar puerto efímero libre al kernel
    let ephemeral = TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(8001);
    (ephemeral, false)
}

#[tauri::command]
fn get_backend_port(state: tauri::State<'_, BackendPort>) -> u16 {
    state.0.load(Ordering::Relaxed)
}

#[tauri::command]
fn toggle_mini_player(app: tauri::AppHandle) -> Result<bool, String> {
    if let Some(mini_window) = app.get_webview_window("mini-player") {
        let is_visible = mini_window.is_visible().map_err(|e| e.to_string())?;
        if is_visible {
            mini_window.hide().map_err(|e| e.to_string())?;
            Ok(false)
        } else {
            mini_window.show().map_err(|e| e.to_string())?;
            let _ = mini_window.set_focus();
            Ok(true)
        }
    } else {
        Err("Mini-player window not found".to_string())
    }
}

#[tauri::command]
fn close_mini_player(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(mini_window) = app.get_webview_window("mini-player") {
        mini_window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn is_mini_player_open(app: tauri::AppHandle) -> Result<bool, String> {
    if let Some(mini_window) = app.get_webview_window("mini-player") {
        mini_window.is_visible().map_err(|e| e.to_string())
    } else {
        Ok(false)
    }
}

#[tauri::command]
fn focus_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(main_window) = app.get_webview_window("main") {
        let _ = main_window.show();
        let _ = main_window.unminimize();
        let _ = main_window.set_focus();
    }
    Ok(())
}

#[tauri::command]
fn start_dragging_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}

fn spawn_backend_process(backend_port: u16) -> Option<Child> {
    let current_pid = std::process::id();

    // En modo desarrollo (debug_assertions), priorizar ejecutar `python backend/run.py` directamente
    #[cfg(debug_assertions)]
    {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        if let Some(workspace_root) = manifest_dir.parent().and_then(|p| p.parent()) {
            let backend_dir = workspace_root.join("backend");
            let run_py = backend_dir.join("run.py");
            if run_py.exists() {
                let py_candidates: Vec<PathBuf> = vec![
                    backend_dir.join(".venv").join("Scripts").join("python.exe"),
                    workspace_root.join(".venv").join("Scripts").join("python.exe"),
                    PathBuf::from("python"),
                    PathBuf::from("py"),
                ];

                for py_bin in py_candidates {
                    let mut cmd = Command::new(&py_bin);
                    cmd.current_dir(&backend_dir)
                        .arg("run.py")
                        .arg("--port")
                        .arg(backend_port.to_string())
                        .arg("--no-reload")
                        .arg("--parent-pid")
                        .arg(current_pid.to_string());
                    #[cfg(windows)]
                    cmd.creation_flags(CREATE_NO_WINDOW);
                    cmd.stdout(Stdio::null());
                    cmd.stderr(Stdio::null());

                    if let Ok(mut child) = cmd.spawn() {
                        std::thread::sleep(Duration::from_millis(80));
                        if let Ok(None) = child.try_wait() {
                            #[cfg(windows)]
                            enable_kill_on_job_close(&child);
                            CHILD_BACKEND_PID.store(child.id(), Ordering::SeqCst);
                            return Some(child);
                        }
                    }
                }
            }
        }
    }

    // En producción (o fallback si Python no está en PATH), iniciar el sidecar compilado
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            let candidates = [
                exe_dir.join("melosync-backend.exe"),
                exe_dir.join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                exe_dir.join("bin").join("melosync-backend-x86_64-pc-windows-msvc.exe"),
                exe_dir.join("bin").join("melosync-backend.exe"),
                exe_dir.join("../../bin/melosync-backend-x86_64-pc-windows-msvc.exe"),
                exe_dir.join("../../../frontend/src-tauri/bin/melosync-backend-x86_64-pc-windows-msvc.exe"),
                exe_dir.join("../../../backend/dist/melosync-backend-x86_64-pc-windows-msvc.exe"),
            ];

            for cand in &candidates {
                if cand.exists() {
                    let mut cmd = Command::new(cand);
                    cmd.arg("--port")
                        .arg(backend_port.to_string())
                        .arg("--no-reload")
                        .arg("--parent-pid")
                        .arg(current_pid.to_string());
                    #[cfg(windows)]
                    cmd.creation_flags(CREATE_NO_WINDOW);
                    cmd.stdout(Stdio::null());
                    cmd.stderr(Stdio::null());

                    if let Ok(child) = cmd.spawn() {
                        #[cfg(windows)]
                        enable_kill_on_job_close(&child);
                        CHILD_BACKEND_PID.store(child.id(), Ordering::SeqCst);
                        return Some(child);
                    }
                }
            }
        }
    }

    None
}

fn kill_backend_process(child: &mut Child) {
    CHILD_BACKEND_PID.store(0, Ordering::SeqCst);
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[cfg(windows)]
    unsafe {
        extern "system" {
            fn SetConsoleCtrlHandler(
                handler_routine: Option<unsafe extern "system" fn(u32) -> i32>,
                add: i32,
            ) -> i32;
        }
        let _ = SetConsoleCtrlHandler(Some(console_ctrl_handler), 1);
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            toggle_mini_player,
            close_mini_player,
            is_mini_player_open,
            focus_main_window,
            start_dragging_window,
            get_backend_port
        ])
        .setup(|app| {
            let (initial_port, already_running) = resolve_backend_port();
            let port_atomic = Arc::new(AtomicU16::new(initial_port));
            app.manage(BackendPort(port_atomic.clone()));

            let backend_child = if already_running {
                None
            } else {
                spawn_backend_process(initial_port)
            };

            // Hilo ligero de sondeo HTTP /health en background: notifica al frontend en cuanto meloSync API responda
            let app_handle = app.handle().clone();
            let probe_port_atomic = port_atomic.clone();
            std::thread::spawn(move || {
                for _ in 0..300 {
                    let target_port = probe_port_atomic.load(Ordering::Relaxed);
                    if is_melosync_healthy(target_port) {
                        let _ = app_handle.emit("backend-ready", target_port);
                        break;
                    }

                    // Verificar también si run.py escribió un puerto activo en ~/.melosync/active_port.json
                    if let Some(disc_port) = read_discovery_port() {
                        if disc_port != target_port && is_melosync_healthy(disc_port) {
                            probe_port_atomic.store(disc_port, Ordering::Relaxed);
                            let _ = app_handle.emit("backend-ready", disc_port);
                            break;
                        }
                    }

                    std::thread::sleep(Duration::from_millis(50));
                }
            });

            // Inicializar la identidad de meloSync en Windows (AUMID, Registro HKCU y Acceso Directo)
            windows_identity::init();

            // Forzar el título limpio 'meloSync' y la aplicación del icono en la ventana y barra de tareas
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_title("meloSync");
                if let Some(icon) = app.default_window_icon() {
                    let _ = window.set_icon(icon.clone());
                }
            }

            app.manage(BackendProcess(Mutex::new(backend_child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == "mini-player" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
            if window.label() == "main" {
                match event {
                    tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed => {
                        if let Some(mini) = window.app_handle().get_webview_window("mini-player") {
                            let _ = mini.destroy();
                        }
                        if let Some(state) = window.app_handle().try_state::<BackendProcess>() {
                            if let Ok(mut lock) = state.0.lock() {
                                if let Some(mut child) = lock.take() {
                                    kill_backend_process(&mut child);
                                }
                            }
                        }
                        window.app_handle().exit(0);
                    }
                    _ => {}
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running meloSync application");
}
