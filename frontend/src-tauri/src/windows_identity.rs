#[cfg(windows)]
use std::env;
#[cfg(windows)]
use std::ffi::OsStr;
#[cfg(windows)]
use std::os::windows::ffi::OsStrExt;
#[cfg(windows)]
use std::path::PathBuf;
#[cfg(windows)]
use std::process::Command;

#[cfg(windows)]
const APP_ID: &str = "com.melosync.desktop";
#[cfg(windows)]
const APP_NAME: &str = "meloSync";

#[cfg(windows)]
type Hkey = *mut std::ffi::c_void;

#[cfg(windows)]
const HKEY_CURRENT_USER: Hkey = (0x80000001_u32 as i32 as isize) as Hkey;
#[cfg(windows)]
const KEY_SET_VALUE: u32 = 0x0002;
#[cfg(windows)]
const REG_SZ: u32 = 1;
#[cfg(windows)]
const REG_DWORD: u32 = 4;
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[cfg(windows)]
#[link(name = "shell32")]
extern "system" {
    fn SetCurrentProcessExplicitAppUserModelID(app_id: *const u16) -> i32;
}

#[cfg(windows)]
#[link(name = "advapi32")]
extern "system" {
    fn RegCreateKeyExW(
        h_key: Hkey,
        lp_sub_key: *const u16,
        reserved: u32,
        lp_class: *mut u16,
        dw_options: u32,
        sam_desired: u32,
        lp_security_attributes: *mut std::ffi::c_void,
        phk_result: *mut Hkey,
        lpdw_disposition: *mut u32,
    ) -> i32;

    fn RegSetValueExW(
        h_key: Hkey,
        lp_value_name: *const u16,
        reserved: u32,
        dw_type: u32,
        lp_data: *const u8,
        cb_data: u32,
    ) -> i32;

    fn RegCloseKey(h_key: Hkey) -> i32;
}

#[cfg(windows)]
fn to_wide_null(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(std::iter::once(0)).collect()
}

pub fn init() {
    #[cfg(windows)]
    {
        // 1. Asignar el AppUserModelID para que Windows SMTC y la barra de tareas identifiquen el proceso
        let wide_id = to_wide_null(APP_ID);
        unsafe {
            let _ = SetCurrentProcessExplicitAppUserModelID(wide_id.as_ptr());
        }

        // 2. Registrar en HKCU\Software\Classes\AppUserModelId\com.melosync.desktop
        // Esto permite que el centro de control multimedia (SMTC) resuelva el DisplayName "meloSync"
        // y el IconUri del ejecutable inmediatamente sin requerir permisos de administrador.
        register_in_registry();

        // 3. Crear / asegurar acceso directo en el Menú Inicio en segundo plano
        ensure_start_menu_shortcut_async();
    }
}

#[cfg(windows)]
fn register_in_registry() {
    let subkey = to_wide_null("Software\\Classes\\AppUserModelId\\com.melosync.desktop");
    let mut hkey: Hkey = std::ptr::null_mut();
    let mut disposition: u32 = 0;

    unsafe {
        let status = RegCreateKeyExW(
            HKEY_CURRENT_USER,
            subkey.as_ptr(),
            0,
            std::ptr::null_mut(),
            0,
            KEY_SET_VALUE,
            std::ptr::null_mut(),
            &mut hkey,
            &mut disposition,
        );

        if status == 0 && !hkey.is_null() {
            // DisplayName = "meloSync"
            let val_name_display = to_wide_null("DisplayName");
            let val_data_display = to_wide_null(APP_NAME);
            let _ = RegSetValueExW(
                hkey,
                val_name_display.as_ptr(),
                0,
                REG_SZ,
                val_data_display.as_ptr() as *const u8,
                (val_data_display.len() * 2) as u32,
            );

            // IconUri = ruta completa al ejecutable melosync.exe
            if let Ok(exe_path) = env::current_exe() {
                let exe_str = exe_path.to_string_lossy();
                let val_name_icon = to_wide_null("IconUri");
                let val_data_icon = to_wide_null(&exe_str);
                let _ = RegSetValueExW(
                    hkey,
                    val_name_icon.as_ptr(),
                    0,
                    REG_SZ,
                    val_data_icon.as_ptr() as *const u8,
                    (val_data_icon.len() * 2) as u32,
                );
            }

            // ShowInSettings = 1 (DWORD)
            let val_name_show = to_wide_null("ShowInSettings");
            let val_data_show: u32 = 1;
            let _ = RegSetValueExW(
                hkey,
                val_name_show.as_ptr(),
                0,
                REG_DWORD,
                &val_data_show as *const u32 as *const u8,
                4,
            );

            RegCloseKey(hkey);
        }
    }
}

#[cfg(windows)]
fn ensure_start_menu_shortcut_async() {
    std::thread::spawn(|| {
        if let Ok(appdata) = env::var("APPDATA") {
            let shortcut_path = PathBuf::from(&appdata)
                .join("Microsoft")
                .join("Windows")
                .join("Start Menu")
                .join("Programs")
                .join("meloSync.lnk");

            let exe_path = match env::current_exe() {
                Ok(p) => p,
                Err(_) => return,
            };

            if !shortcut_path.exists() {
                let shortcut_str = shortcut_path.to_string_lossy();
                let exe_str = exe_path.to_string_lossy();

                let ps_script = format!(
                    "$ws = New-Object -ComObject WScript.Shell; \
                     $s = $ws.CreateShortcut('{shortcut}'); \
                     $s.TargetPath = '{target}'; \
                     $s.Save();",
                    shortcut = shortcut_str.replace('\'', "''"),
                    target = exe_str.replace('\'', "''")
                );

                use std::os::windows::process::CommandExt;
                let mut cmd = Command::new("powershell");
                cmd.creation_flags(CREATE_NO_WINDOW);
                cmd.arg("-NoProfile")
                    .arg("-NonInteractive")
                    .arg("-Command")
                    .arg(&ps_script);
                let _ = cmd.status();
            }
        }
    });
}

