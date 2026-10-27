//! clyffy-avatar-shell — the desktop surface for the live face.
//!
//! Roadmap E2: "a face in a separate window on laptop/phone". This is the laptop half.
//! It is a SHELL, not the face: it owns window placement, transparency and always-on-top,
//! and nothing else. The face itself is `../renderer` (three-vrm, drive contract v1), and
//! the state it reacts to comes from clyffyd `GET /avatar/state`.
//!
//! Deliberate window choices:
//!   * `transparent` + `decorations:false` — a companion sits ON the desktop, not in a
//!     chrome-framed box. Requires a compositor; on a bare X11 session with no compositing
//!     the background falls back to opaque black rather than failing.
//!   * `alwaysOnTop` — it is an assistant; it is useless behind the IDE.
//!   * `skipTaskbar` — a companion is not an app you alt-tab to.
//!   * `focus:false` — appearing must never steal focus from what the operator is typing in.
//!
//! Placement is bottom-right (operator: "bottom-right on the computer"), computed at
//! runtime from the CURRENT monitor rather than hardcoded, so it lands correctly on any
//! resolution and survives a monitor change.

use tauri::{Manager, PhysicalPosition};

/// Gap from the screen edges, in logical pixels.
const MARGIN: f64 = 24.0;

fn main() {
    // ⚠️ MUST be set before WebKit initialises, which is why it is the first statement.
    //
    // WebKitGTK's DMABUF renderer fails on this box with
    //     KMS: DRM_IOCTL_MODE_CREATE_DUMB failed: Permission denied
    //     Failed to create GBM buffer of size 420x560: Permission denied
    // and the window renders EMPTY — a fully transparent hole, which looks identical to
    // "the app didn't start". Note this is NOT a plain permissions problem: ACLs do grant
    // this user rw on /dev/dri/card0 AND renderD128. It is the known WebKitGTK-on-NVIDIA
    // DMABUF path. Disabling it costs nothing measurable here — WebGL still runs the
    // avatar on the GPU (60 fps in the browser on the same stack).
    //
    // Set here rather than documented in a README because a required env var that lives
    // only in someone's shell history is a bug waiting to happen.
    if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        // SAFETY: single-threaded, before any WebKit/GTK initialisation.
        unsafe { std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1") };
    }

    tauri::Builder::default()
        .setup(|app| {
            let Some(win) = app.get_webview_window("face") else {
                eprintln!("clyffy-avatar-shell: no window labelled 'face'");
                return Ok(());
            };
            // Park it bottom-right of whichever monitor it opened on. Every value here is
            // PHYSICAL pixels — mixing logical and physical is how these end up off-screen
            // on a scaled display.
            match win.current_monitor() {
                Ok(Some(mon)) => {
                    let screen = mon.size();
                    let scale = mon.scale_factor();
                    let pos = mon.position();
                    match win.outer_size() {
                        Ok(w) => {
                            let m = (MARGIN * scale).round() as i32;
                            let x = pos.x + screen.width as i32 - w.width as i32 - m;
                            let y = pos.y + screen.height as i32 - w.height as i32 - m;
                            if let Err(e) = win.set_position(PhysicalPosition::new(x, y)) {
                                eprintln!("clyffy-avatar-shell: set_position failed: {e}");
                            }
                        }
                        Err(e) => eprintln!("clyffy-avatar-shell: outer_size failed: {e}"),
                    }
                }
                // No monitor info (headless/odd WM): leave the window where the WM put it
                // rather than guessing coordinates that could land it off-screen.
                Ok(None) => eprintln!("clyffy-avatar-shell: no current monitor; leaving placement to the WM"),
                Err(e) => eprintln!("clyffy-avatar-shell: current_monitor failed: {e}"),
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("clyffy-avatar-shell: failed to run");
}
