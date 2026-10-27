import bmesh
unsel()
o = obj()
bpy.context.view_layer.objects.active = o
for x in bpy.context.view_layer.objects: x.select_set(False)
o.select_set(True)
if bpy.context.mode != "OBJECT": bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.mode_set(mode="EDIT")
bpy.context.tool_settings.mesh_select_mode = (False, True, False)
bm = bmesh.from_edit_mesh(o.data)
def key(e):
    m = (e.verts[0].co + e.verts[1].co) / 2
    return (round(m.x, 5), round(m.y, 5), round(m.z, 5))
w, a = _view3d(); reg = [r for r in a.regions if r.type == "WINDOW"][0]
v0, f0 = len(bm.verts), len(bm.faces)
bpy.ops.mesh.select_all(action="DESELECT")
n = sum(1 for e in bm.edges if key(e) in UPKEYS and (e.select_set(True) or True))
bm.select_flush(True); bmesh.update_edit_mesh(o.data)
with bpy.context.temp_override(window=w, area=a, region=reg):
    r1 = bpy.ops.mesh.fill_grid(span=17, offset=0, use_interp_simple=False)
bm = bmesh.from_edit_mesh(o.data)
out.append("upper: selected %d, fill %s, verts %d -> %d, faces %d -> %d" %
           (n, r1, v0, len(bm.verts), f0, len(bm.faces)))
v1, f1 = len(bm.verts), len(bm.faces)
bpy.ops.mesh.select_all(action="DESELECT")
m = sum(1 for e in bm.edges if key(e) in LOKEYS and (e.select_set(True) or True))
bm.select_flush(True); bmesh.update_edit_mesh(o.data)
with bpy.context.temp_override(window=w, area=a, region=reg):
    r2 = bpy.ops.mesh.fill_grid(span=15, offset=0, use_interp_simple=False)
bm = bmesh.from_edit_mesh(o.data)
out.append("lower: selected %d, fill %s, verts %d -> %d, faces %d -> %d" %
           (m, r2, v1, len(bm.verts), f1, len(bm.faces)))
bpy.ops.object.mode_set(mode="OBJECT")
result = stat()
