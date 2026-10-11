"""Render a hero still of a lit set:  blender -b -P render_still.py -- <lit.blend> <out.jpg> <cam x,y,z> <target x,y,z> [samples] [width] [height]"""
import bpy, sys
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
blend, out, cam, tgt = a[0], a[1], tuple(map(float, a[2].split(","))), tuple(map(float, a[3].split(",")))
spp, w, h = (int(a[4]) if len(a) > 4 else 48), (int(a[5]) if len(a) > 5 else 1600), (int(a[6]) if len(a) > 6 else 900)
bpy.ops.wm.open_mainfile(filepath=blend)
s = bpy.context.scene
cd = bpy.data.cameras.new("hero"); cd.lens = 20
c = bpy.data.objects.new("hero", cd); s.collection.objects.link(c); c.location = cam
c.rotation_euler = (Vector(tgt) - Vector(cam)).to_track_quat("-Z", "Y").to_euler(); s.camera = c
s.render.engine = "CYCLES"; s.cycles.samples = spp
try:
    s.cycles.use_denoising = True; s.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    s.cycles.use_denoising = False
s.view_settings.view_transform = "AgX" if "AgX" in [i.name for i in type(s.view_settings).bl_rna.properties["view_transform"].enum_items] else "Filmic"
s.view_settings.look = "None"
s.render.resolution_x, s.render.resolution_y = w, h
s.render.image_settings.file_format = "JPEG"; s.render.image_settings.quality = 82
s.render.filepath = out
bpy.ops.render.render(write_still=True)
