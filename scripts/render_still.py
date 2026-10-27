"""Headless still render: blender -b FILE.blend --python scripts/render_still.py -- OUT.png

Env: CLYFFY_ENGINE (CYCLES|BLENDER_EEVEE|BLENDER_WORKBENCH, default CYCLES),
     CLYFFY_CYCLES_DEVICE (CPU|CUDA|OPTIX, default CPU), CLYFFY_SAMPLES (default 32),
     CLYFFY_RES (WxH, default 768x768), CLYFFY_DENOISE (1 = OIDN on, default off).
A GPU device that cannot be initialised falls back to CPU instead of failing.
"""
import os, sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = os.path.abspath(argv[0] if argv else "out/render.png")
scene = bpy.context.scene
engine = os.environ.get("CLYFFY_ENGINE", "CYCLES")
scene.render.engine = engine
w, h = (int(v) for v in os.environ.get("CLYFFY_RES", "768x768").lower().split("x"))
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = out

if engine == "CYCLES":
    scene.cycles.samples = int(os.environ.get("CLYFFY_SAMPLES", "32"))
    # OpenImageDenoise is off by default: some Blender builds (incl. the native ARM64 one)
    # ship without a working OIDN CPU device. Opt in with CLYFFY_DENOISE=1.
    denoise = os.environ.get("CLYFFY_DENOISE", "0") == "1"
    scene.cycles.use_denoising = denoise
    for vl in scene.view_layers:
        vl.cycles.use_denoising = denoise
    want = os.environ.get("CLYFFY_CYCLES_DEVICE", "CPU").upper()
    used = "CPU"
    if want != "CPU":
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = want
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == want]
            for d in prefs.devices:
                d.use = d.type == want
            if gpus:
                scene.cycles.device = "GPU"
                used = f"{want} ({', '.join(d.name for d in gpus)})"
        except Exception as e:  # no driver / no kernel for this GPU
            print(f"[clyffy] {want} unavailable ({e}); falling back to CPU", flush=True)
    print(f"[clyffy] Cycles device: {used}", flush=True)

if scene.camera is None:
    cams = [o for o in scene.objects if o.type == "CAMERA"]
    if cams:
        scene.camera = cams[0]
    else:
        bpy.ops.object.camera_add(location=(0, -4, 1.2), rotation=(1.45, 0, 0))
        scene.camera = bpy.context.object

bpy.ops.render.render(write_still=True)
print(f"[clyffy] wrote {out}", flush=True)
