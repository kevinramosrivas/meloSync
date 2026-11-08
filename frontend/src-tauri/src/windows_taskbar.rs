//! Windows Taskbar Thumbnail Toolbar & Progress Integration
//!
//! Provides interactive media controls (Previous, Play/Pause, Next) embedded directly in the
//! Windows Taskbar live thumbnail preview (ITaskbarList3::ThumbBarAddButtons), taskbar icon progress,
//! window title synchronization (Spotify-style "Title • Artist"), and thumbnail tooltips.
//!
//! Fully cross-platform: compiles native Win32 FFI on Windows and safe no-op stubs on Linux/macOS.

#[cfg(target_os = "windows")]
pub mod implementation {
    use std::ffi::c_void;
    use std::sync::Mutex;
    use tauri::{AppHandle, Emitter, Manager, WebviewWindow};

    const CLSID_TASKBAR_LIST: [u8; 16] = [
        0x44, 0xF3, 0xFD, 0x56, 0x6D, 0xFD, 0xd0, 0x11, 0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90,
    ];
    const IID_ITASKBAR_LIST3: [u8; 16] = [
        0x91, 0xfb, 0x1a, 0xea, 0x28, 0x9e, 0x86, 0x4b, 0x90, 0xe9, 0x9e, 0x9f, 0x8a, 0x5e, 0xef, 0xaf,
    ];

    const THBM_ICON: u32 = 0x00000002;
    const THBM_TOOLTIP: u32 = 0x00000004;
    const THBM_FLAGS: u32 = 0x00000008;

    const THBF_ENABLED: u32 = 0x00000000;
    const THBF_DISABLED: u32 = 0x00000001;

    const THBN_CLICKED: u16 = 0x1800;
    const WM_COMMAND: u32 = 0x0111;

    pub const TBPF_NOPROGRESS: u32 = 0x00000000;
    pub const TBPF_NORMAL: u32 = 0x00000002;
    pub const TBPF_PAUSED: u32 = 0x00000008;

    pub const BUTTON_PREV: u32 = 100;
    pub const BUTTON_PLAY_PAUSE: u32 = 101;
    pub const BUTTON_NEXT: u32 = 102;

    const SUBCLASS_ID: usize = 0x4D535943; // 'MSYC'

    type Hresult = i32;

    #[repr(C)]
    struct ITaskbarList3Vtbl {
        // IUnknown
        query_interface: unsafe extern "system" fn(*mut c_void, *const u8, *mut *mut c_void) -> Hresult,
        add_ref: unsafe extern "system" fn(*mut c_void) -> u32,
        release: unsafe extern "system" fn(*mut c_void) -> u32,
        // ITaskbarList
        hr_init: unsafe extern "system" fn(*mut c_void) -> Hresult,
        add_tab: unsafe extern "system" fn(*mut c_void, *mut c_void) -> Hresult,
        delete_tab: unsafe extern "system" fn(*mut c_void, *mut c_void) -> Hresult,
        activate_tab: unsafe extern "system" fn(*mut c_void, *mut c_void) -> Hresult,
        set_active_alt: unsafe extern "system" fn(*mut c_void, *mut c_void) -> Hresult,
        // ITaskbarList2
        mark_fullscreen_window: unsafe extern "system" fn(*mut c_void, *mut c_void, i32) -> Hresult,
        // ITaskbarList3
        set_progress_value: unsafe extern "system" fn(*mut c_void, *mut c_void, u64, u64) -> Hresult,
        set_progress_state: unsafe extern "system" fn(*mut c_void, *mut c_void, u32) -> Hresult,
        register_tab: unsafe extern "system" fn(*mut c_void, *mut c_void, *mut c_void) -> Hresult,
        unregister_tab: unsafe extern "system" fn(*mut c_void, *mut c_void) -> Hresult,
        set_tab_order: unsafe extern "system" fn(*mut c_void, *mut c_void, *mut c_void) -> Hresult,
        set_tab_active: unsafe extern "system" fn(*mut c_void, *mut c_void, *mut c_void, u32) -> Hresult,
        thumb_bar_add_buttons: unsafe extern "system" fn(*mut c_void, *mut c_void, u32, *const ThumbButton) -> Hresult,
        thumb_bar_update_buttons: unsafe extern "system" fn(*mut c_void, *mut c_void, u32, *const ThumbButton) -> Hresult,
        set_thumbnail_tooltip: unsafe extern "system" fn(*mut c_void, *mut c_void, *const u16) -> Hresult,
        set_thumbnail_clip: unsafe extern "system" fn(*mut c_void, *mut c_void, *const c_void) -> Hresult,
    }

    #[repr(C)]
    struct ITaskbarList3 {
        vtbl: *const ITaskbarList3Vtbl,
    }

    #[repr(C)]
    pub struct ThumbButton {
        pub dw_mask: u32,
        pub i_id: u32,
        pub i_bitmap: u32,
        pub h_icon: *mut c_void,
        pub sz_tip: [u16; 260],
        pub dw_flags: u32,
    }

    #[link(name = "ole32")]
    extern "system" {
        fn CoInitializeEx(pv_reserved: *mut c_void, dw_co_init: u32) -> Hresult;
        fn CoCreateInstance(
            rclsid: *const u8,
            p_unk_outer: *mut c_void,
            dw_cls_context: u32,
            riid: *const u8,
            ppv: *mut *mut c_void,
        ) -> Hresult;
    }

    #[link(name = "user32")]
    extern "system" {
        fn CreateIconFromResourceEx(
            pb_icon_bits: *const u8,
            cb_icon_bits: u32,
            f_icon: i32,
            dw_version: u32,
            cx_desired: i32,
            cy_desired: i32,
            u_flags: u32,
        ) -> *mut c_void;
        #[allow(dead_code)]
        fn DestroyIcon(h_icon: *mut c_void) -> i32;
        fn SetWindowTextW(h_wnd: *mut c_void, lp_string: *const u16) -> i32;
    }

    #[link(name = "comctl32")]
    extern "system" {
        fn SetWindowSubclass(
            h_wnd: *mut c_void,
            pfn_subclass: Option<SubclassProc>,
            u_id_subclass: usize,
            dw_ref_data: usize,
        ) -> i32;
        fn DefSubclassProc(
            h_wnd: *mut c_void,
            u_msg: u32,
            w_param: usize,
            l_param: isize,
        ) -> isize;
    }

    type SubclassProc = unsafe extern "system" fn(
        h_wnd: *mut c_void,
        u_msg: u32,
        w_param: usize,
        l_param: isize,
        u_id_subclass: usize,
        dw_ref_data: usize,
    ) -> isize;

    // Static global app handle reference for the subclass procedure
    static GLOBAL_APP_HANDLE: Mutex<Option<AppHandle>> = Mutex::new(None);

    unsafe extern "system" fn taskbar_subclass_proc(
        h_wnd: *mut c_void,
        u_msg: u32,
        w_param: usize,
        l_param: isize,
        _u_id_subclass: usize,
        _dw_ref_data: usize,
    ) -> isize {
        if u_msg == WM_COMMAND {
            let notify_code = ((w_param >> 16) & 0xFFFF) as u16;
            let button_id = (w_param & 0xFFFF) as u32;

            if notify_code == THBN_CLICKED {
                if let Ok(guard) = GLOBAL_APP_HANDLE.lock() {
                    if let Some(ref app) = *guard {
                        match button_id {
                            BUTTON_PREV => {
                                let _ = app.emit("taskbar-previous", ());
                            }
                            BUTTON_PLAY_PAUSE => {
                                let _ = app.emit("taskbar-toggle-play", ());
                            }
                            BUTTON_NEXT => {
                                let _ = app.emit("taskbar-next", ());
                            }
                            _ => {}
                        }
                    }
                }
                return 0;
            }
        }
        DefSubclassProc(h_wnd, u_msg, w_param, l_param)
    }

    // Embed icon bytes at compile-time directly in the binary
    static ICO_PREV: &[u8] = include_bytes!("../icons/taskbar/prev.ico");
    static ICO_PLAY: &[u8] = include_bytes!("../icons/taskbar/play.ico");
    static ICO_PAUSE: &[u8] = include_bytes!("../icons/taskbar/pause.ico");
    static ICO_NEXT: &[u8] = include_bytes!("../icons/taskbar/next.ico");

    fn load_icon_from_ico_bytes(bytes: &[u8], preferred_size: u8) -> *mut c_void {
        if bytes.len() < 6 {
            return std::ptr::null_mut();
        }
        let count = u16::from_le_bytes([bytes[4], bytes[5]]) as usize;
        let mut best_offset = 0usize;
        let mut best_size = 0usize;
        let mut best_diff = u8::MAX;

        for i in 0..count {
            let entry_offset = 6 + i * 16;
            if entry_offset + 16 > bytes.len() {
                break;
            }
            let w = bytes[entry_offset];
            let diff = (w as i16 - preferred_size as i16).abs() as u8;
            if diff < best_diff {
                best_diff = diff;
                let size = u32::from_le_bytes([
                    bytes[entry_offset + 8],
                    bytes[entry_offset + 9],
                    bytes[entry_offset + 10],
                    bytes[entry_offset + 11],
                ]) as usize;
                let offset = u32::from_le_bytes([
                    bytes[entry_offset + 12],
                    bytes[entry_offset + 13],
                    bytes[entry_offset + 14],
                    bytes[entry_offset + 15],
                ]) as usize;
                best_size = size;
                best_offset = offset;
            }
        }

        if best_size == 0 || best_offset + best_size > bytes.len() {
            return std::ptr::null_mut();
        }

        let slice = &bytes[best_offset..best_offset + best_size];
        unsafe {
            CreateIconFromResourceEx(
                slice.as_ptr(),
                slice.len() as u32,
                1,          // 1 = icon
                0x00030000, // Windows version
                0,
                0,
                0,
            )
        }
    }

    struct WindowEntry {
        label: String,
        hwnd: *mut c_void,
        buttons_added: bool,
    }

    struct TaskbarState {
        taskbar_list: *mut ITaskbarList3,
        windows: Vec<WindowEntry>,
        icon_prev: *mut c_void,
        icon_play: *mut c_void,
        icon_pause: *mut c_void,
        icon_next: *mut c_void,
        current_title: Option<String>,
        current_artist: Option<String>,
        last_is_playing: bool,
        last_can_prev: bool,
        last_can_next: bool,
        last_pos: u64,
        last_dur: u64,
    }

    unsafe impl Send for TaskbarState {}
    unsafe impl Sync for TaskbarState {}

    static TASKBAR_STATE: Mutex<Option<TaskbarState>> = Mutex::new(None);

    fn to_sz_tip(text: &str) -> [u16; 260] {
        let mut buf = [0u16; 260];
        for (i, c) in text.encode_utf16().take(259).enumerate() {
            buf[i] = c;
        }
        buf
    }

    fn to_wide_null_terminated(text: &str) -> Vec<u16> {
        text.encode_utf16().chain(std::iter::once(0)).collect()
    }

    pub fn format_title(label: &str, title: Option<&str>, artist: Option<&str>) -> String {
        match title {
            Some(t) if !t.trim().is_empty() => {
                match artist {
                    Some(a) if !a.trim().is_empty() => format!("{t} • {a}"),
                    _ => t.to_string(),
                }
            }
            _ => {
                if label == "mini-player" {
                    "meloSync Mini Player".to_string()
                } else {
                    "meloSync".to_string()
                }
            }
        }
    }

    fn build_buttons(
        icon_prev: *mut c_void,
        play_pause_icon: *mut c_void,
        icon_next: *mut c_void,
        is_playing: bool,
        can_previous: bool,
        can_next: bool,
    ) -> [ThumbButton; 3] {
        let play_pause_tip = if is_playing { "Pausar" } else { "Reproducir" };
        [
            ThumbButton {
                dw_mask: THBM_ICON | THBM_TOOLTIP | THBM_FLAGS,
                i_id: BUTTON_PREV,
                i_bitmap: 0,
                h_icon: icon_prev,
                sz_tip: to_sz_tip("Anterior"),
                dw_flags: if can_previous { THBF_ENABLED } else { THBF_DISABLED },
            },
            ThumbButton {
                dw_mask: THBM_ICON | THBM_TOOLTIP | THBM_FLAGS,
                i_id: BUTTON_PLAY_PAUSE,
                i_bitmap: 0,
                h_icon: play_pause_icon,
                sz_tip: to_sz_tip(play_pause_tip),
                dw_flags: THBF_ENABLED,
            },
            ThumbButton {
                dw_mask: THBM_ICON | THBM_TOOLTIP | THBM_FLAGS,
                i_id: BUTTON_NEXT,
                i_bitmap: 0,
                h_icon: icon_next,
                sz_tip: to_sz_tip("Siguiente"),
                dw_flags: if can_next { THBF_ENABLED } else { THBF_DISABLED },
            },
        ]
    }

    unsafe fn apply_buttons_to_window(
        taskbar: *mut ITaskbarList3,
        window: &mut WindowEntry,
        buttons: &[ThumbButton; 3],
    ) {
        if !window.buttons_added {
            let hr = ((*(*taskbar).vtbl).thumb_bar_add_buttons)(
                taskbar as *mut c_void,
                window.hwnd,
                3,
                buttons.as_ptr(),
            );
            if hr == 0 {
                window.buttons_added = true;
            }
        } else {
            let _ = ((*(*taskbar).vtbl).thumb_bar_update_buttons)(
                taskbar as *mut c_void,
                window.hwnd,
                3,
                buttons.as_ptr(),
            );
        }
    }

    unsafe fn apply_progress_to_window(
        taskbar: *mut ITaskbarList3,
        hwnd: *mut c_void,
        position_secs: u64,
        duration_secs: u64,
        is_playing: bool,
    ) {
        if duration_secs > 0 {
            let progress_flag = if is_playing { TBPF_NORMAL } else { TBPF_PAUSED };
            let _ = ((*(*taskbar).vtbl).set_progress_state)(taskbar as *mut c_void, hwnd, progress_flag);
            let _ = ((*(*taskbar).vtbl).set_progress_value)(
                taskbar as *mut c_void,
                hwnd,
                position_secs,
                duration_secs,
            );
        } else {
            let _ = ((*(*taskbar).vtbl).set_progress_state)(taskbar as *mut c_void, hwnd, TBPF_NOPROGRESS);
        }
    }

    pub fn init_taskbar_on_window(window: &WebviewWindow) -> Result<(), String> {
        let raw_hwnd = window.hwnd().map_err(|e| e.to_string())?.0 as *mut c_void;
        let label = window.label().to_string();

        let mut lock = TASKBAR_STATE.lock().map_err(|e| e.to_string())?;

        // Store AppHandle for window subclass events
        if let Ok(mut handle_guard) = GLOBAL_APP_HANDLE.lock() {
            if handle_guard.is_none() {
                *handle_guard = Some(window.app_handle().clone());
            }
        }

        if lock.is_none() {
            unsafe {
                // Initialize COM library for this thread
                let _ = CoInitializeEx(std::ptr::null_mut(), 0x0002 /* COINIT_APARTMENTTHREADED */);

                let mut taskbar_ptr: *mut c_void = std::ptr::null_mut();
                let hr = CoCreateInstance(
                    CLSID_TASKBAR_LIST.as_ptr(),
                    std::ptr::null_mut(),
                    1, // CLSCTX_INPROC_SERVER
                    IID_ITASKBAR_LIST3.as_ptr(),
                    &mut taskbar_ptr,
                );

                if hr != 0 || taskbar_ptr.is_null() {
                    return Err(format!("Failed to create ITaskbarList3 instance: 0x{:08X}", hr));
                }

                let taskbar = taskbar_ptr as *mut ITaskbarList3;
                let hr_init = ((*(*taskbar).vtbl).hr_init)(taskbar as *mut c_void);
                if hr_init != 0 {
                    return Err(format!("Failed to initialize ITaskbarList3: 0x{:08X}", hr_init));
                }

                // Load icons (prefer 24x24 / 20x20 crisp icons)
                let icon_prev = load_icon_from_ico_bytes(ICO_PREV, 20);
                let icon_play = load_icon_from_ico_bytes(ICO_PLAY, 20);
                let icon_pause = load_icon_from_ico_bytes(ICO_PAUSE, 20);
                let icon_next = load_icon_from_ico_bytes(ICO_NEXT, 20);

                *lock = Some(TaskbarState {
                    taskbar_list: taskbar,
                    windows: Vec::new(),
                    icon_prev,
                    icon_play,
                    icon_pause,
                    icon_next,
                    current_title: None,
                    current_artist: None,
                    last_is_playing: false,
                    last_can_prev: false,
                    last_can_next: false,
                    last_pos: 0,
                    last_dur: 0,
                });
            }
        }

        let state = match lock.as_mut() {
            Some(s) => s,
            None => return Ok(()),
        };

        // Check if window already registered
        let existing_index = state.windows.iter().position(|w| w.hwnd == raw_hwnd);
        let window_idx = match existing_index {
            Some(idx) => idx,
            None => {
                unsafe {
                    SetWindowSubclass(raw_hwnd, Some(taskbar_subclass_proc), SUBCLASS_ID, 0);
                }
                state.windows.push(WindowEntry {
                    label: label.clone(),
                    hwnd: raw_hwnd,
                    buttons_added: false,
                });
                state.windows.len() - 1
            }
        };

        // Apply cached state to this window immediately
        unsafe {
            let taskbar = state.taskbar_list;
            let play_pause_icon = if state.last_is_playing {
                state.icon_pause
            } else {
                state.icon_play
            };

            let buttons = build_buttons(
                state.icon_prev,
                play_pause_icon,
                state.icon_next,
                state.last_is_playing,
                state.last_can_prev,
                state.last_can_next,
            );

            apply_buttons_to_window(taskbar, &mut state.windows[window_idx], &buttons);

            apply_progress_to_window(
                taskbar,
                raw_hwnd,
                state.last_pos,
                state.last_dur,
                state.last_is_playing,
            );

            // Apply cached track title & tooltip
            let formatted_title = format_title(
                &label,
                state.current_title.as_deref(),
                state.current_artist.as_deref(),
            );
            let wide_title = to_wide_null_terminated(&formatted_title);
            SetWindowTextW(raw_hwnd, wide_title.as_ptr());
            let _ = window.set_title(&formatted_title);

            if state.current_title.is_some() {
                let wide_tip = to_wide_null_terminated(&formatted_title);
                let _ = ((*(*taskbar).vtbl).set_thumbnail_tooltip)(
                    taskbar as *mut c_void,
                    raw_hwnd,
                    wide_tip.as_ptr(),
                );
            } else {
                let _ = ((*(*taskbar).vtbl).set_thumbnail_tooltip)(
                    taskbar as *mut c_void,
                    raw_hwnd,
                    std::ptr::null(),
                );
            }
        }

        Ok(())
    }

    pub fn update_track(
        app: &AppHandle,
        title: Option<String>,
        artist: Option<String>,
    ) -> Result<(), String> {
        let mut lock = TASKBAR_STATE.lock().map_err(|e| e.to_string())?;
        let state = match lock.as_mut() {
            Some(s) => s,
            None => return Ok(()),
        };

        state.current_title = title.clone();
        state.current_artist = artist.clone();

        unsafe {
            let taskbar = state.taskbar_list;
            for w in &state.windows {
                let win_title = format_title(&w.label, title.as_deref(), artist.as_deref());
                let wide_title = to_wide_null_terminated(&win_title);
                SetWindowTextW(w.hwnd, wide_title.as_ptr());

                if let Some(win) = app.get_webview_window(&w.label) {
                    let _ = win.set_title(&win_title);
                }

                if title.is_some() {
                    let wide_tip = to_wide_null_terminated(&win_title);
                    let _ = ((*(*taskbar).vtbl).set_thumbnail_tooltip)(
                        taskbar as *mut c_void,
                        w.hwnd,
                        wide_tip.as_ptr(),
                    );
                } else {
                    let _ = ((*(*taskbar).vtbl).set_thumbnail_tooltip)(
                        taskbar as *mut c_void,
                        w.hwnd,
                        std::ptr::null(),
                    );
                }
            }
        }

        Ok(())
    }

    pub fn update_playback(
        _window: &WebviewWindow,
        is_playing: bool,
        can_previous: bool,
        can_next: bool,
    ) -> Result<(), String> {
        let mut lock = TASKBAR_STATE.lock().map_err(|e| e.to_string())?;
        let state = match lock.as_mut() {
            Some(s) => s,
            None => return Ok(()),
        };

        state.last_is_playing = is_playing;
        state.last_can_prev = can_previous;
        state.last_can_next = can_next;

        let play_pause_icon = if is_playing {
            state.icon_pause
        } else {
            state.icon_play
        };

        let buttons = build_buttons(
            state.icon_prev,
            play_pause_icon,
            state.icon_next,
            is_playing,
            can_previous,
            can_next,
        );

        unsafe {
            let taskbar = state.taskbar_list;
            for w in &mut state.windows {
                apply_buttons_to_window(taskbar, w, &buttons);
            }
        }

        Ok(())
    }

    pub fn set_progress(
        _window: &WebviewWindow,
        position_secs: u64,
        duration_secs: u64,
        is_playing: bool,
    ) -> Result<(), String> {
        let mut lock = TASKBAR_STATE.lock().map_err(|e| e.to_string())?;
        let state = match lock.as_mut() {
            Some(s) => s,
            None => return Ok(()),
        };

        state.last_pos = position_secs;
        state.last_dur = duration_secs;
        state.last_is_playing = is_playing;

        unsafe {
            let taskbar = state.taskbar_list;
            for w in &state.windows {
                apply_progress_to_window(taskbar, w.hwnd, position_secs, duration_secs, is_playing);
            }
        }

        Ok(())
    }

    pub fn clear_progress(_window: &WebviewWindow) -> Result<(), String> {
        let mut lock = TASKBAR_STATE.lock().map_err(|e| e.to_string())?;
        let state = match lock.as_mut() {
            Some(s) => s,
            None => return Ok(()),
        };

        state.last_pos = 0;
        state.last_dur = 0;

        unsafe {
            let taskbar = state.taskbar_list;
            for w in &state.windows {
                let _ = ((*(*taskbar).vtbl).set_progress_state)(taskbar as *mut c_void, w.hwnd, TBPF_NOPROGRESS);
            }
        }

        Ok(())
    }
}

// ----------------------------------------------------------------------------
// TAURI COMMANDS (Cross-platform wrappers)
// ----------------------------------------------------------------------------

#[tauri::command]
pub fn init_taskbar_controls(window: tauri::WebviewWindow) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        implementation::init_taskbar_on_window(&window)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = window;
        Ok(())
    }
}

#[tauri::command]
pub fn update_taskbar_track(
    app: tauri::AppHandle,
    title: Option<String>,
    artist: Option<String>,
) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        implementation::update_track(&app, title, artist)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app, title, artist);
        Ok(())
    }
}

#[tauri::command]
pub fn update_taskbar_playback(
    window: tauri::WebviewWindow,
    is_playing: bool,
    can_previous: bool,
    can_next: bool,
) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        implementation::update_playback(&window, is_playing, can_previous, can_next)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (window, is_playing, can_previous, can_next);
        Ok(())
    }
}

#[tauri::command]
pub fn update_taskbar_progress(
    window: tauri::WebviewWindow,
    position_secs: u64,
    duration_secs: u64,
    is_playing: bool,
) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        implementation::set_progress(&window, position_secs, duration_secs, is_playing)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (window, position_secs, duration_secs, is_playing);
        Ok(())
    }
}

#[tauri::command]
pub fn clear_taskbar_progress(window: tauri::WebviewWindow) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        implementation::clear_progress(&window)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = window;
        Ok(())
    }
}

#[tauri::command]
pub fn get_desktop_platform() -> String {
    #[cfg(target_os = "windows")]
    {
        "windows".to_string()
    }
    #[cfg(target_os = "linux")]
    {
        "linux".to_string()
    }
    #[cfg(target_os = "macos")]
    {
        "macos".to_string()
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        "unknown".to_string()
    }
}
