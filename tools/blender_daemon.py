"""A live Blender session I can drive by signal, that the operator can see and take over.

    blender work/RETOPO_clyffy.blend --python tools/blender_daemon.py

WHY. Every edit so far has been `blender -b --python one_shot.py`: cold start, parse a 13 MB .blend,
run one script, write a PNG, throw the process away. Thirty to sixty seconds a step, and the only
feedback is a picture that has to be interpreted by eye. That is why a fin 0.0008 units wide took
six passes to find — the mesh was never asked, it was only photographed.

This is the operator's design: keep Blender ALIVE, drive it over a socket, and get STRUCTURED
answers back instead of screenshots. Renders become something requested when eyes are actually
needed, not the only sense available.

It runs with the UI up on DISPLAY :0 on purpose. The operator watches the same session change under
his cursor and can take the mouse at any moment — no export, no handoff, no "send me the file".

THREADING. `bpy` is not thread-safe and touching it off the main thread corrupts Blender silently.
So the socket server thread only ever ENQUEUES; a `bpy.app.timers` callback on the main thread does
all the work and hands the reply back. The client blocks until that round trip completes, which
makes every command synchronous from the outside and single-threaded on the inside.
"""
import bpy, socket, threading, queue, json, os, sys, traceback

SOCK = os.environ.get("CLYFFY_BL_SOCK", "/tmp/clyffy_blender.sock")
_in = queue.Queue()
_ns = {"bpy": bpy}          # persists between commands — this is the point of a live session
JOURNAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "work", "bl_journal.jsonl")

# Load the toolkit ONCE into the namespace so every command can call stat(), loops(), shot(),
# snap(), narrow_faces() and the rest by name. This is what turns the unit of work from "a script"
# into "a question".
_KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blkit.py")
_ns["__file__"] = _KIT       # exec'd code has no __file__ of its own; blkit derives its paths from it
try:
    exec(compile(open(_KIT).read(), _KIT, "exec"), _ns)
    print(f"[clyffy] toolkit loaded: "
          f"{', '.join(k for k in sorted(_ns) if not k.startswith('_'))[:200]}", flush=True)
except Exception:
    traceback.print_exc()


def _server():
    try:
        if os.path.exists(SOCK):
            os.remove(SOCK)
    except OSError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(SOCK)
    s.listen(8)
    print(f"[clyffy] blender daemon listening on {SOCK}", flush=True)
    while True:
        try:
            conn, _ = s.accept()
            buf = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            reply = queue.Queue()
            _in.put((buf.decode("utf-8"), reply))
            conn.sendall(reply.get().encode("utf-8"))   # blocks on the main thread's answer
            conn.close()
        except Exception:
            traceback.print_exc()


def _jsonable(v, depth=0):
    """Best-effort JSON: numbers and strings pass, Blender types become readable summaries."""
    if depth > 6:
        return "<deep>"
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x, depth + 1) for x in list(v)[:2000]]
    if isinstance(v, dict):
        return {str(k): _jsonable(x, depth + 1) for k, x in list(v.items())[:2000]}
    if hasattr(v, "__len__") and hasattr(v, "__getitem__") and not isinstance(v, str):
        try:
            return [_jsonable(x, depth + 1) for x in list(v)[:2000]]
        except Exception:
            pass
    return repr(v)


def _pump():
    while True:
        try:
            code, reply = _in.get_nowait()
        except queue.Empty:
            return 0.02
        out = {"ok": True}
        t0 = __import__("time").time()
        try:
            _ns["result"] = None
            _ns["out"] = []
            exec(compile(code, "<cmd>", "exec"), _ns)
            out["result"] = _jsonable(_ns.get("result"))
            if _ns.get("out"):
                out["out"] = _jsonable(_ns["out"])
        except Exception:
            out["ok"] = False
            out["error"] = traceback.format_exc(limit=6)
        out["ms"] = int((__import__("time").time() - t0) * 1000)
        # JOURNAL EVERY COMMAND. A live session's history is otherwise only in my head, and this
        # project has already lost work to that. The journal is what makes a session reconstructible
        # — the same reason clyffy treats the journal as truth and the indices as derived.
        try:
            with open(JOURNAL, "a") as jf:
                jf.write(json.dumps({"t": __import__("time").time(), "ms": out["ms"],
                                     "ok": out["ok"], "code": code[:4000],
                                     "err": out.get("error", "")[:500]}) + "\n")
        except OSError:
            pass
        try:
            reply.put(json.dumps(out))
        except (TypeError, ValueError):
            reply.put(json.dumps({"ok": True, "result": repr(_ns.get("result"))}))


bpy.app.timers.register(_pump, persistent=True)
threading.Thread(target=_server, daemon=True).start()
print("[clyffy] daemon armed", flush=True)
