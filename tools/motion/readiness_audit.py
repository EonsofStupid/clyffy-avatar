res = {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH": continue
    sk = ob.data.shape_keys
    res[ob.name] = {"verts": len(ob.data.vertices),
                    "shape_keys": [k.name for k in sk.key_blocks] if sk else [],
                    "materials": [m.name for m in ob.data.materials if m],
                    "uv_layers": [u.name for u in ob.data.uv_layers]}
rig = bpy.data.objects["clyffy_rig"]
res["_rig"] = {"bones": [b.name for b in rig.data.bones],
               "actions": [a.name for a in bpy.data.actions],
               "has_eye_bones": any("eye" in b.name.lower() for b in rig.data.bones),
               "has_lid_bones": any("lid" in b.name.lower() or "blink" in b.name.lower()
                                    for b in rig.data.bones)}
res["_scene"] = {"images": [i.name for i in bpy.data.images if i.name != "Render Result"][:12]}
result = res
