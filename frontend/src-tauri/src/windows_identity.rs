#[cfg(windows)]
use std::env;
#[cfg(windows)]
use std::ffi::OsStr;
#[cfg(windows)]
use std::fs;
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
static ICON_ICO_BYTES: &[u8] = include_bytes!("../icons/icon.ico");

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
        // 1. Asignar el AppUserModelID al proceso lo antes posible
        let wide_id = to_wide_null(APP_ID);
        unsafe {
            let _ = SetCurrentProcessExplicitAppUserModelID(wide_id.as_ptr());
        }

        // 2. Extraer permanentemente el icono meloSync a %LOCALAPPDATA%\meloSync\icon.ico
        let icon_path = ensure_persisted_icon();

        // 3. Registrar en el Registro de Windows:
        //    - HKCU\Software\Classes\AppUserModelId\com.melosync.desktop
        //    - HKCU\Software\Classes\Applications\melosync.exe
        //    Esto permite que Windows SMTC (Control Center flyout) y la barra de tareas identifiquen
        //    inmediatamente "meloSync" y su icono oficial sin permisos de administrador.
        register_in_registry(icon_path.as_deref());

        // 4. Crear o actualizar el acceso directo en el Menú Inicio con PKEY_AppUserModel_ID
        ensure_start_menu_shortcut_async(icon_path);
    }
}

#[cfg(windows)]
fn ensure_persisted_icon() -> Option<String> {
    if let Ok(local_app_data) = env::var("LOCALAPPDATA") {
        let dir = PathBuf::from(&local_app_data).join("meloSync");
        let _ = fs::create_dir_all(&dir);
        let icon_file = dir.join("icon.ico");
        if !icon_file.exists() || fs::metadata(&icon_file).map(|m| m.len()).unwrap_or(0) == 0 {
            let _ = fs::write(&icon_file, ICON_ICO_BYTES);
        }
        return Some(icon_file.to_string_lossy().to_string());
    }
    None
}

#[cfg(windows)]
fn set_reg_sz(hkey: Hkey, name: &str, val: &str) {
    let name_wide = to_wide_null(name);
    let val_wide = to_wide_null(val);
    unsafe {
        let _ = RegSetValueExW(
            hkey,
            name_wide.as_ptr(),
            0,
            REG_SZ,
            val_wide.as_ptr() as *const u8,
            (val_wide.len() * 2) as u32,
        );
    }
}

#[cfg(windows)]
fn set_reg_dword(hkey: Hkey, name: &str, val: u32) {
    let name_wide = to_wide_null(name);
    unsafe {
        let _ = RegSetValueExW(
            hkey,
            name_wide.as_ptr(),
            0,
            REG_DWORD,
            &val as *const u32 as *const u8,
            4,
        );
    }
}

#[cfg(windows)]
fn register_in_registry(icon_path: Option<&str>) {
    let icon_str = icon_path.map(|s| s.to_string()).unwrap_or_else(|| {
        if let Ok(exe_path) = env::current_exe() {
            format!("{},0", exe_path.to_string_lossy())
        } else {
            String::new()
        }
    });

    // 1. HKCU\Software\Classes\AppUserModelId\com.melosync.desktop
    let subkey_aumid = to_wide_null("Software\\Classes\\AppUserModelId\\com.melosync.desktop");
    let mut hkey: Hkey = std::ptr::null_mut();
    let mut disposition: u32 = 0;

    unsafe {
        let status = RegCreateKeyExW(
            HKEY_CURRENT_USER,
            subkey_aumid.as_ptr(),
            0,
            std::ptr::null_mut(),
            0,
            KEY_SET_VALUE,
            std::ptr::null_mut(),
            &mut hkey,
            &mut disposition,
        );

        if status == 0 && !hkey.is_null() {
            set_reg_sz(hkey, "DisplayName", APP_NAME);
            set_reg_sz(hkey, "IconUri", &icon_str);
            set_reg_sz(hkey, "IconBackgroundColor", "00000000");
            set_reg_dword(hkey, "ShowInSettings", 1);
            RegCloseKey(hkey);
        }
    }

    // 2. HKCU\Software\Classes\Applications\melosync.exe
    let subkey_app = to_wide_null("Software\\Classes\\Applications\\melosync.exe");
    unsafe {
        let mut hkey_app: Hkey = std::ptr::null_mut();
        let status = RegCreateKeyExW(
            HKEY_CURRENT_USER,
            subkey_app.as_ptr(),
            0,
            std::ptr::null_mut(),
            0,
            KEY_SET_VALUE,
            std::ptr::null_mut(),
            &mut hkey_app,
            &mut disposition,
        );

        if status == 0 && !hkey_app.is_null() {
            set_reg_sz(hkey_app, "FriendlyAppName", APP_NAME);
            set_reg_sz(hkey_app, "ApplicationCompany", APP_NAME);
            RegCloseKey(hkey_app);
        }

        // DefaultIcon
        let subkey_icon = to_wide_null("Software\\Classes\\Applications\\melosync.exe\\DefaultIcon");
        let mut hkey_icon: Hkey = std::ptr::null_mut();
        let status_icon = RegCreateKeyExW(
            HKEY_CURRENT_USER,
            subkey_icon.as_ptr(),
            0,
            std::ptr::null_mut(),
            0,
            KEY_SET_VALUE,
            std::ptr::null_mut(),
            &mut hkey_icon,
            &mut disposition,
        );

        if status_icon == 0 && !hkey_icon.is_null() {
            let icon_formatted = if icon_str.ends_with(".ico") {
                format!("{icon_str},0")
            } else {
                icon_str.clone()
            };
            set_reg_sz(hkey_icon, "", &icon_formatted);
            RegCloseKey(hkey_icon);
        }
    }
}

#[cfg(windows)]
fn ensure_start_menu_shortcut_async(icon_path: Option<String>) {
    std::thread::spawn(move || {
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

            let shortcut_str = shortcut_path.to_string_lossy();
            let exe_str = exe_path.to_string_lossy();
            let icon_str = icon_path.unwrap_or_else(|| exe_str.to_string());

            // Script con IPropertyStore y PKEY_AppUserModel_ID ({9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, 5)
            // Esto vincula irrevocablemente el acceso directo del Menú Inicio con el AUMID "com.melosync.desktop"
            // permitiendo que Windows SMTC muestre el nombre "meloSync" y el icono oficial en vez de "Aplicación desconocida".
            let ps_script = format!(
                r#"
                $code = @'
                using System;
                using System.IO;
                using System.Runtime.InteropServices;
                using System.Runtime.InteropServices.ComTypes;

                public static class LnkUpdater {{
                    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
                    private class CShellLink {{}}

                    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
                    private interface IShellLinkW {{
                        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszFile, int cchMaxPath, IntPtr pfd, uint fFlags);
                        void GetIDList(out IntPtr ppidl);
                        void SetIDList(IntPtr pidl);
                        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszName, int cchMaxName);
                        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
                        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszDir, int cchMaxPath);
                        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
                        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszArgs, int cchMaxPath);
                        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
                        void GetHotkey(out short pwHotkey);
                        void SetHotkey(short wHotkey);
                        void GetShowCmd(out int piShowCmd);
                        void SetShowCmd(int iShowCmd);
                        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszIconPath, int cchIconPath, out int piIcon);
                        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
                        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, uint dwReserved);
                        void Resolve(IntPtr hwnd, uint fFlags);
                        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
                    }}

                    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
                    private interface IPropertyStore {{
                        int GetCount(out uint cProps);
                        int GetAt(uint iProp, out PROPERTYKEY pkey);
                        int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
                        int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
                        int Commit();
                    }}

                    [StructLayout(LayoutKind.Sequential, Pack=4)]
                    private struct PROPERTYKEY {{
                        public Guid fmtid;
                        public uint pid;
                    }}

                    [StructLayout(LayoutKind.Sequential)]
                    private struct PROPVARIANT {{
                        public ushort vt;
                        public ushort w1, w2, w3;
                        public IntPtr p;
                        public int i1, i2;
                    }}

                    public static void CreateOrUpdate(string shortcutPath, string targetPath, string iconPath, string appId) {{
                        CShellLink link = new CShellLink();
                        IShellLinkW shellLink = (IShellLinkW)link;
                        shellLink.SetPath(targetPath);
                        shellLink.SetWorkingDirectory(Path.GetDirectoryName(targetPath));
                        if (!string.IsNullOrEmpty(iconPath)) {{
                            shellLink.SetIconLocation(iconPath, 0);
                        }}

                        IPropertyStore propStore = (IPropertyStore)link;
                        PROPERTYKEY pkey = new PROPERTYKEY {{
                            fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"),
                            pid = 5
                        }};

                        PROPVARIANT pv = new PROPVARIANT();
                        pv.vt = 31;
                        pv.p = Marshal.StringToCoTaskMemUni(appId);

                        propStore.SetValue(ref pkey, ref pv);
                        propStore.Commit();
                        Marshal.FreeCoTaskMem(pv.p);

                        IPersistFile persistFile = (IPersistFile)link;
                        persistFile.Save(shortcutPath, true);
                    }}
                }}
                '@;
                Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue;
                [LnkUpdater]::CreateOrUpdate('{shortcut}', '{target}', '{icon}', '{app_id}');
                "#,
                shortcut = shortcut_str.replace('\'', "''"),
                target = exe_str.replace('\'', "''"),
                icon = icon_str.replace('\'', "''"),
                app_id = APP_ID
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
    });
}
