"""Alexandria sets — built in Blender, lit and baked in Cycles, exported as glTF for the web and VR Hall (and Unreal).

    blender -b -P build_sets.py -- --scene presidents --out ./out            # quick bake (web)
    blender -b -P build_sets.py -- --scene hall --out ./out --res 2048 --samples 256 --gpu   # base1 RTX 5080, high quality

Scenes
  hall        The Great Hall: a marble rotunda with a coffered dome and oculus, 24 fluted columns and 10 niches.
              NICHE_0 is the doorway to the Hall of Presidents, NICHE_1..8 hold the subject shelves, NICHE_9 the screen.
  presidents  The Hall of Presidents: a theater with a proscenium arch, velvet curtains, a lectern and
              47 pedestals on three curved tiers (P01..P47).
Empties named like that are exported as anchors: the app puts live content (books, names, screens, speeches) on them.
Every lit surface is baked (Cycles, combined light) into its own texture, so the scene looks rendered on any device.
"""
import bpy, bmesh, math, sys, os, argparse, time
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="hall", choices=["hall", "presidents", "reading", "stair"])
ap.add_argument("--out", default="out")
ap.add_argument("--res", type=int, default=1024)
ap.add_argument("--samples", type=int, default=40)
ap.add_argument("--gpu", action="store_true")
ap.add_argument("--nobake", action="store_true")
ap.add_argument("--unreal", action="store_true", help="bake surface colour only and keep the lights: Unreal (Lumen) lights it")
A = ap.parse_args(argv)
os.makedirs(A.out, exist_ok=True)
T0 = time.time()


def log(*m):
    print(f"[{time.time() - T0:6.1f}s]", *m, flush=True)


# ------------------------------------------------------------------ reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = A.samples
scene.cycles.use_denoising = False
if A.gpu:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for t in ("OPTIX", "CUDA", "HIP"):
            try:
                prefs.compute_device_type = t
                prefs.refresh_devices()
                if any(d.type == t for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == t
                    scene.cycles.device = "GPU"
                    log("GPU", t)
                    break
            except TypeError:
                pass
    except Exception as e:
        log("no GPU:", e)
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.014, 0.02, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0


# ------------------------------------------------------------------ materials (procedural; baked to textures at the end)
def mat(name, kind, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emit=0.0, extra=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    tc = N.new("ShaderNodeTexCoord")
    if kind == "marble":
        noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 2.2; noise.inputs["Detail"].default_value = 12
        noise.inputs["Distortion"].default_value = 1.4
        wave = N.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 1.6; wave.inputs["Distortion"].default_value = 9
        wave.inputs["Detail"].default_value = 8
        L.new(tc.outputs["Object"], noise.inputs["Vector"]); L.new(noise.outputs["Color"], wave.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*[c * 0.55 for c in color], 1)
        ramp.color_ramp.elements[1].position = 0.12; ramp.color_ramp.elements[1].color = (*color, 1)
        L.new(wave.outputs["Fac"], ramp.inputs["Fac"]); L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    elif kind == "wood":
        wave = N.new("ShaderNodeTexWave"); wave.wave_type = "RINGS"; wave.inputs["Scale"].default_value = 3
        wave.inputs["Distortion"].default_value = 6; wave.inputs["Detail"].default_value = 4
        L.new(tc.outputs["Object"], wave.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*[c * 0.6 for c in color], 1); ramp.color_ramp.elements[1].color = (*color, 1)
        L.new(wave.outputs["Fac"], ramp.inputs["Fac"]); L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    elif kind == "velvet":
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        for k in ("Sheen Weight", "Sheen"):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = 1.0
        if "Sheen Tint" in bsdf.inputs and bsdf.inputs["Sheen Tint"].type == "RGBA":
            bsdf.inputs["Sheen Tint"].default_value = (1, 0.55, 0.55, 1)
    elif kind == "plaster":
        noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 30; noise.inputs["Detail"].default_value = 6
        L.new(tc.outputs["Object"], noise.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*[c * 0.9 for c in color], 1); ramp.color_ramp.elements[1].color = (*color, 1)
        L.new(noise.outputs["Fac"], ramp.inputs["Fac"]); L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1)
    if emit:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


M = {
    "marble": mat("marble", "marble", (0.92, 0.89, 0.83), 0.22),
    "marble_dark": mat("marble_dark", "marble", (0.10, 0.17, 0.14), 0.2),
    "marble_red": mat("marble_red", "marble", (0.42, 0.12, 0.08), 0.25),
    "gold": mat("gold", "flat", (0.86, 0.64, 0.26), 0.28, 1.0),
    "plaster": mat("plaster", "plaster", (0.86, 0.80, 0.68), 0.8),
    "royal": mat("royal", "plaster", (0.07, 0.10, 0.22), 0.7),
    "coffer": mat("coffer", "plaster", (0.78, 0.70, 0.55), 0.7),
    "wood": mat("wood", "wood", (0.30, 0.15, 0.07), 0.45),
    "velvet": mat("velvet", "velvet", (0.36, 0.02, 0.04), 0.9),
    "shelf": mat("shelf", "wood", (0.22, 0.11, 0.05), 0.6),
    "glow": mat("glow", "flat", (1.0, 0.82, 0.55), 0.5, 0, emit=25),
    "sky": mat("sky", "flat", (0.55, 0.68, 0.95), 0.5, 0, emit=3),
    "glowblue": mat("glowblue", "flat", (0.55, 0.72, 1.0), 0.5, 0, emit=18),
    "skylight": mat("skylight", "flat", (0.62, 0.74, 0.92), 0.5, 0, emit=2.6),   # big panes stay soft: no glare (eye comfort)
    "walnut": mat("walnut", "wood", (0.26, 0.12, 0.05), 0.4),
    "oak": mat("oak", "wood", (0.42, 0.24, 0.11), 0.5),
    "brass": mat("brass", "flat", (0.78, 0.58, 0.25), 0.35, 1.0),
    "fresco_blue": mat("fresco_blue", "plaster", (0.16, 0.28, 0.52), 0.8),
    "fresco_gold": mat("fresco_gold", "plaster", (0.80, 0.62, 0.28), 0.6),
    "fresco_rose": mat("fresco_rose", "plaster", (0.62, 0.34, 0.26), 0.7),
    "rug": mat("rug", "marble", (0.45, 0.10, 0.08), 0.95),
    "tapestry": mat("tapestry", "marble", (0.38, 0.33, 0.22), 0.95),
    "books_a": mat("books_a", "wood", (0.40, 0.10, 0.07), 0.7),
    "books_b": mat("books_b", "wood", (0.12, 0.22, 0.16), 0.7),
    "books_c": mat("books_c", "wood", (0.42, 0.32, 0.14), 0.7),
    "glass": mat("glass", "flat", (0.75, 0.85, 0.9), 0.05),
    "screen": mat("screen", "flat", (0.02, 0.02, 0.025), 0.4),
}
GROUPS = {}          # bake group -> list of objects


def put(obj, group, m):
    obj.data.materials.clear()
    obj.data.materials.append(M[m])
    GROUPS.setdefault(group, []).append(obj)
    return obj


def link(obj):
    bpy.context.collection.objects.link(obj)
    return obj


def mesh_from_bm(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def cyl(name, r, h, seg=32, loc=(0, 0, 0), r2=None, group="misc", m="marble", flutes=0, cap=True):
    bm = bmesh.new()
    rr = r2 if r2 is not None else r
    ring_b, ring_t = [], []
    for i in range(seg):
        a = i / seg * math.tau
        f = (1 - 0.06 * (0.5 + 0.5 * math.cos(a * flutes))) if flutes else 1
        ring_b.append(bm.verts.new((math.cos(a) * r * f, math.sin(a) * r * f, 0)))
        ring_t.append(bm.verts.new((math.cos(a) * rr * f, math.sin(a) * rr * f, h)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((ring_b[i], ring_b[j], ring_t[j], ring_t[i]))
    if cap:
        bm.faces.new(list(reversed(ring_b)))
        bm.faces.new(ring_t)
    o = mesh_from_bm(name, bm)
    o.location = loc
    for p in o.data.polygons:
        p.use_smooth = True
    return put(o, group, m)


def box(name, size, loc, group="misc", m="marble", rot=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    o = mesh_from_bm(name, bm)
    o.location = loc
    o.rotation_euler[2] = rot
    return put(o, group, m)


def ring(name, r_in, r_out, z, seg=96, group="floor", m="marble", a0=0.0, a1=math.tau, h=0.0):
    bm = bmesh.new()
    n = seg
    ins, outs, ins2, outs2 = [], [], [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        ins.append(bm.verts.new((math.cos(a) * r_in, math.sin(a) * r_in, z + h)))
        outs.append(bm.verts.new((math.cos(a) * r_out, math.sin(a) * r_out, z + h)))
    for i in range(n):
        if (a1 - a0) >= math.tau - 1e-6 and i == n - 1:
            bm.faces.new((ins[i], outs[i], outs[0], ins[0]))
        else:
            bm.faces.new((ins[i], outs[i], outs[i + 1], ins[i + 1]))
    if h:
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            ins2.append(bm.verts.new((math.cos(a) * r_in, math.sin(a) * r_in, z)))
            outs2.append(bm.verts.new((math.cos(a) * r_out, math.sin(a) * r_out, z)))
        for i in range(n):
            bm.faces.new((outs[i], outs2[i], outs2[i + 1], outs[i + 1]))
            bm.faces.new((ins2[i], ins[i], ins[i + 1], ins2[i + 1]))
    o = mesh_from_bm(name, bm)
    return put(o, group, m)


def anchor(name, loc, face_center=True, rotz=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.location = loc
    if rotz is not None:
        e.rotation_euler[2] = rotz
    elif face_center:
        e.rotation_euler[2] = math.atan2(-loc[1], -loc[0]) - math.pi / 2     # local -Y faces the centre
    link(e)
    return e


def light(kind, loc, energy, color=(1, 0.86, 0.66), size=1.0, rot=None, spot=None):
    ld = bpy.data.lights.new(f"L_{kind}", kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    if kind == "SPOT" and spot:
        ld.spot_size = spot
        ld.spot_blend = 0.6
    if kind == "POINT":
        ld.shadow_soft_size = size
    o = link(bpy.data.objects.new(ld.name, ld))
    o.location = loc
    if rot:
        o.rotation_euler = rot
    return o


def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------------ THE GREAT HALL
def build_hall():
    R = 13.0
    # floor: concentric bands of marble with a gold compass ring
    ring("floor_center", 0.0001, 2.2, 0, 96, "floor", "marble_dark")
    ring("floor_gold1", 2.2, 2.32, 0.002, 96, "trim", "gold")
    ring("floor_band1", 2.32, 5.4, 0, 96, "floor", "marble")
    ring("floor_band2", 5.4, 5.9, 0, 96, "floor", "marble_red")
    ring("floor_band3", 5.9, 9.6, 0, 96, "floor", "marble")
    ring("floor_gold2", 9.6, 9.7, 0.002, 96, "trim", "gold")
    ring("floor_outer", 9.7, R + 2.5, 0, 96, "floor", "marble_dark")
    # compass star in the centre
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0.004))
    pts = []
    for i in range(16):
        a = i / 16 * math.tau
        r = 2.0 if i % 2 == 0 else 0.55
        pts.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, 0.004)))
    for i in range(16):
        bm.faces.new((c, pts[i], pts[(i + 1) % 16]))
    put(mesh_from_bm("compass", bm), "trim", "gold")
    # wall with 10 niches
    wall_r, wall_h = R + 2.2, 9.0
    seg = 120
    bm = bmesh.new()
    niche_half = math.radians(8)
    NN = 12
    verts = []
    for i in range(seg + 1):
        a = i / seg * math.tau
        verts.append((bm.verts.new((math.cos(a) * wall_r, math.sin(a) * wall_r, 0)), bm.verts.new((math.cos(a) * wall_r, math.sin(a) * wall_r, wall_h))))
    for i in range(seg):
        a = (i + 0.5) / seg * math.tau
        if any(abs(((a - k * math.tau / 10 + math.pi) % math.tau) - math.pi) < niche_half for k in range(NN)):
            # opening: wall only above the niche arch
            b0, t0 = verts[i]; b1, t1 = verts[i + 1]
            m0 = bm.verts.new((b0.co.x, b0.co.y, 5.2)); m1 = bm.verts.new((b1.co.x, b1.co.y, 5.2))
            bm.faces.new((m0, m1, t1, t0))
        else:
            b0, t0 = verts[i]; b1, t1 = verts[i + 1]
            bm.faces.new((b0, b1, t1, t0))
    o = mesh_from_bm("wall", bm)
    o.data.flip_normals() if hasattr(o.data, "flip_normals") else None
    put(o, "walls", "plaster")
    for p in o.data.polygons:
        p.use_smooth = True
    # niches: back wall, shelves frame, arch
    for k in range(NN):
        a = k * math.tau / NN
        cx, cy = math.cos(a), math.sin(a)
        depth = 2.0
        back = box(f"niche_back_{k}", (0.3, 2 * wall_r * math.sin(niche_half), 5.2), ((wall_r + depth) * cx, (wall_r + depth) * cy, 2.6), "walls", "plaster", rot=a)
        for side in (-1, 1):
            sa = a + side * niche_half
            box(f"niche_side_{k}_{side}", (depth, 0.3, 5.2), ((wall_r + depth / 2) * math.cos(sa), (wall_r + depth / 2) * math.sin(sa), 2.6), "walls", "plaster", rot=a)
        box(f"niche_top_{k}", (depth, 2 * wall_r * math.sin(niche_half) + 0.3, 0.3), ((wall_r + depth / 2) * cx, (wall_r + depth / 2) * cy, 5.25), "walls", "coffer", rot=a)
        box(f"niche_floor_{k}", (depth + 0.4, 2 * wall_r * math.sin(niche_half), 0.08), ((wall_r + depth / 2) * cx, (wall_r + depth / 2) * cy, 0.04), "floor", "wood", rot=a)
        if k in (0, 10, 11):     # doorways: 0 Hall of Presidents, 10 Reading Room, 11 Archive Stair
            for side in (-1, 1):
                sa = a + side * niche_half * 0.75
                box(f"door_drape_{k}_{side}", (0.2, 0.9, 5.0), ((wall_r + 0.4) * math.cos(sa), (wall_r + 0.4) * math.sin(sa), 2.5), "drapes", "velvet", rot=a)
            box(f"door_glow_{k}", (0.05, 2 * wall_r * math.sin(niche_half) * 0.7, 4.6), ((wall_r + depth - 0.2) * cx, (wall_r + depth - 0.2) * cy, 2.4), "glow" if k != 11 else "glowblue", "glow" if k != 11 else "glowblue", rot=a)
        elif k == 9:   # screening wall
            box("screen_frame", (0.15, 4.2, 2.6), ((wall_r + depth - 0.25) * cx, (wall_r + depth - 0.25) * cy, 2.7), "trim", "gold", rot=a)
            box("screen_face", (0.05, 3.9, 2.3), ((wall_r + depth - 0.34) * cx, (wall_r + depth - 0.34) * cy, 2.7), "misc", "screen", rot=a)
        else:          # bookshelves
            for row in range(4):
                box(f"shelf_{k}_{row}", (0.45, 3.6, 0.06), ((wall_r + depth - 0.4) * cx, (wall_r + depth - 0.4) * cy, 0.6 + row * 1.0), "shelves", "shelf", rot=a)
            box(f"shelf_back_{k}", (0.06, 3.7, 4.2), ((wall_r + depth - 0.17) * cx, (wall_r + depth - 0.17) * cy, 2.2), "shelves", "shelf", rot=a)
        anchor(f"NICHE_{k}", ((wall_r + 0.2) * cx, (wall_r + 0.2) * cy, 0))
        light("POINT", ((wall_r + 0.8) * cx, (wall_r + 0.8) * cy, 4.4), 40, size=0.4)
    # columns
    for i in range(24):
        a = (i + 0.5) / 24 * math.tau
        x, y = math.cos(a) * R, math.sin(a) * R
        cyl(f"col_{i}", 0.42, 7.2, 28, (x, y, 0.5), 0.36, "columns", "marble", flutes=14)
        box(f"col_base_{i}", (1.1, 1.1, 0.5), (x, y, 0.25), "columns", "marble", rot=a)
        cyl(f"col_cap_{i}", 0.42, 0.45, 28, (x, y, 7.7), 0.62, "columns", "gold")
    # entablature + dome
    ring("entab", R - 0.7, wall_r + 0.1, 8.15, 120, "dome", "coffer", h=0.85)
    ring("entab_gold", R - 0.75, R - 0.62, 8.15, 120, "trim", "gold", h=0.9)
    bm = bmesh.new()
    rows, cols = 9, 40
    dome_r, base_z = wall_r + 0.1, 9.0
    grid = []
    for j in range(rows + 1):
        el = j / rows * (math.pi / 2 * 0.86)
        rr, zz = dome_r * math.cos(el), base_z + dome_r * 0.62 * math.sin(el)
        grid.append([bm.verts.new((math.cos(i / cols * math.tau) * rr, math.sin(i / cols * math.tau) * rr, zz)) for i in range(cols)])
    for j in range(rows):
        for i in range(cols):
            f = bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][(i + 1) % cols], grid[j][(i + 1) % cols]))
    bmesh.ops.inset_individual(bm, faces=list(bm.faces), thickness=0.18, depth=-0.22)
    o = mesh_from_bm("dome", bm)
    put(o, "dome", "coffer")
    top_r = dome_r * math.cos(math.pi / 2 * 0.86)
    ring("oculus_rim", top_r - 0.01, top_r + 0.4, base_z + dome_r * 0.62 * math.sin(math.pi / 2 * 0.86), 64, "trim", "gold")
    ring("oculus_sky", 0.0001, top_r, base_z + dome_r * 0.62 * math.sin(math.pi / 2 * 0.86) + 0.6, 64, "sky", "sky")
    # central pedestal for the tutor orb
    cyl("orb_pedestal", 0.75, 1.0, 40, (0, 0, 0), 0.55, "columns", "marble_dark")
    cyl("orb_ring", 0.6, 0.06, 40, (0, 0, 1.0), 0.6, "trim", "gold")
    anchor("ORB", (0, 0, 1.55), rotz=0)
    anchor("SPAWN", (0, -6.5, 0), rotz=0)
    # light: sun through the oculus + warm fill
    sun = light("SPOT", (0, 0, 20), 1100, (1.0, 0.95, 0.85), spot=math.radians(40))
    aim(sun, (0, 0, 0))
    for i in range(6):
        a = i / 6 * math.tau
        light("POINT", (math.cos(a) * 7, math.sin(a) * 7, 7.5), 110, size=1.5)
    light("POINT", (0, 0, 4), 60, size=2)


# ------------------------------------------------------------------ THE HALL OF PRESIDENTS (theater)
def build_presidents():
    # auditorium floor + aisles
    ring("aud_floor", 0.0001, 26, 0, 96, "floor", "marble_dark", a0=math.pi, a1=math.tau)
    ring("aud_floor_front", 0.0001, 26, 0, 96, "floor", "marble_dark", a0=0, a1=math.pi)
    for r0 in (5.0, 9.0, 13.0):
        ring(f"aisle_{r0}", r0, r0 + 0.12, 0.003, 96, "trim", "gold", a0=math.pi * 1.02, a1=math.tau * 0.99)
    # stage: raised half disc at +Y, wood top, marble face
    stage_r, stage_h = 11.0, 1.0
    ring("stage_top", 0.0001, stage_r, stage_h, 96, "stage", "wood", a0=0, a1=math.pi)
    bm = bmesh.new()
    n = 96
    top, bot = [], []
    for i in range(n + 1):
        a = i / n * math.pi
        top.append(bm.verts.new((math.cos(a) * stage_r, math.sin(a) * stage_r, stage_h)))
        bot.append(bm.verts.new((math.cos(a) * stage_r, math.sin(a) * stage_r, 0)))
    for i in range(n):
        bm.faces.new((bot[i], bot[i + 1], top[i + 1], top[i]))
    put(mesh_from_bm("stage_face", bm), "stage", "marble_red")
    ring("stage_lip", stage_r - 0.06, stage_r + 0.06, stage_h, 96, "trim", "gold", a0=0, a1=math.pi, h=0.06)
    # three curved tiers for 47 pedestals
    tiers = [(5.0, 0.35, 13), (7.0, 0.75, 16), (9.0, 1.15, 18)]
    n_global = 1
    for t, (r, h, count) in enumerate(tiers):
        ring(f"tier_{t}", r - 0.8, r + 0.8, stage_h, 96, "tiers", "marble", a0=math.radians(14), a1=math.radians(166), h=h)
        for i in range(count):
            a = math.radians(18) + (math.radians(144)) * (i / (count - 1))
            x, y = math.cos(a) * r, math.sin(a) * r
            z0 = stage_h + h
            cyl(f"ped_{n_global:02d}", 0.32, 0.9, 24, (x, y, z0), 0.28, "pedestals", "marble", flutes=10)
            cyl(f"ped_cap_{n_global:02d}", 0.38, 0.1, 24, (x, y, z0 + 0.9), 0.38, "pedestals", "gold")
            anchor(f"P{n_global:02d}", (x, y, z0 + 1.0))
            n_global += 1
    # back wall (curved), pilasters, proscenium arch
    bm = bmesh.new()
    n = 64
    wr, wh = 12.5, 11.0
    lower, upper = [], []
    for i in range(n + 1):
        a = i / n * math.pi
        lower.append(bm.verts.new((math.cos(a) * wr, math.sin(a) * wr, 0)))
        upper.append(bm.verts.new((math.cos(a) * wr, math.sin(a) * wr, wh)))
    for i in range(n):
        bm.faces.new((lower[i + 1], lower[i], upper[i], upper[i + 1]))
    put(mesh_from_bm("back_wall", bm), "walls", "royal")
    for i in range(9):
        a = math.radians(10 + i * 20)
        box(f"pilaster_{i}", (0.5, 0.3, wh), (math.cos(a) * (wr - 0.15), math.sin(a) * (wr - 0.15), wh / 2), "pilasters", "gold", rot=a + math.pi / 2)
    ring("wall_band_low", wr - 0.25, wr - 0.05, 2.6, 64, "pilasters", "gold", a0=0, a1=math.pi, h=0.12)
    ring("wall_band_high", wr - 0.25, wr - 0.05, 9.6, 64, "pilasters", "gold", a0=0, a1=math.pi, h=0.12)
    # proscenium: two towers + arch beam at the stage front (y ~ 0)
    for side in (-1, 1):
        box(f"pros_tower_{side}", (1.6, 1.6, 12), (side * 12.2, 0.4, 6), "pros", "marble_red")
        box(f"pros_gold_{side}", (0.2, 1.7, 12), (side * 11.35, 0.4, 6), "trim", "gold")
        # velvet curtain swag: folded panel
        bm = bmesh.new()
        cols, rows = 40, 20
        grid = []
        for j in range(rows + 1):
            z = 1.0 + j / rows * 10.5
            gather = 1.0 - 0.55 * (1 - j / rows) ** 2          # tied back near the bottom
            row = []
            for i in range(cols + 1):
                u = i / cols
                x = side * (11.2 - u * 3.6 * gather)
                y = 0.9 + 0.22 * math.sin(u * 26) * (0.6 + 0.4 * j / rows)
                row.append(bm.verts.new((x, y, z)))
            grid.append(row)
        for j in range(rows):
            for i in range(cols):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        o = mesh_from_bm(f"curtain_{side}", bm)
        for p in o.data.polygons:
            p.use_smooth = True
        put(o, "drapes", "velvet")
    box("pros_arch", (26, 1.6, 1.8), (0, 0.4, 12.6), "pros", "marble_red")
    box("pros_arch_gold", (22.6, 1.7, 0.25), (0, 0.4, 11.7), "trim", "gold")
    # valance: velvet header
    bm = bmesh.new()
    cols = 120
    top_row = [bm.verts.new((-11.3 + i / cols * 22.6, 0.95 + 0.12 * math.sin(i * 0.9), 11.6)) for i in range(cols + 1)]
    bot_row = [bm.verts.new((-11.3 + i / cols * 22.6, 0.95 + 0.12 * math.sin(i * 0.9), 10.2 + 0.35 * abs(math.sin(i / cols * math.pi * 7)))) for i in range(cols + 1)]
    for i in range(cols):
        bm.faces.new((bot_row[i], bot_row[i + 1], top_row[i + 1], top_row[i]))
    o = mesh_from_bm("valance", bm)
    for p in o.data.polygons:
        p.use_smooth = True
    put(o, "drapes", "velvet")
    # lectern at the front of the stage
    box("lectern_body", (1.0, 0.6, 1.15), (0, 2.2, stage_h + 0.575), "lectern", "wood")
    box("lectern_top", (1.15, 0.75, 0.08), (0, 2.15, stage_h + 1.2), "lectern", "wood", rot=0)
    box("lectern_plate", (0.5, 0.02, 0.5), (0, 1.89, stage_h + 0.65), "trim", "gold")
    anchor("LECTERN", (0, 2.0, stage_h + 1.25), rotz=0)
    # ceiling with coffers over the stage
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=14, y_segments=8, size=1)
    bmesh.ops.scale(bm, vec=Vector((13, 7, 1)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, 6, 13.6)), verts=bm.verts)
    bmesh.ops.inset_individual(bm, faces=list(bm.faces), thickness=0.12, depth=0.25)
    put(mesh_from_bm("ceiling", bm), "dome", "coffer")
    # chandeliers (emissive)
    for x in (-6, 0, 6):
        cyl(f"chand_{x}", 0.9, 0.15, 24, (x, 6, 11.4), 0.5, "trim", "gold")
        for k in range(8):
            a = k / 8 * math.tau
            cyl(f"bulb_{x}_{k}", 0.07, 0.14, 8, (x + math.cos(a) * 0.8, 6 + math.sin(a) * 0.8, 11.55), 0.05, "glow", "glow")
        light("POINT", (x, 6, 11.0), 700, size=0.8)
    # audience seats hint: rows of benches facing the stage
    for row, r in enumerate((15, 17.5, 20)):
        for i in range(9):
            a = math.pi * 1.12 + i / 8 * math.pi * 0.76
            box(f"bench_{row}_{i}", (2.0, 0.6, 0.5), (math.cos(a) * r, math.sin(a) * r, 0.25), "seats", "velvet", rot=a + math.pi / 2)
    # lights: footlights + spot on the tiers + key on the lectern
    for x in range(-9, 10, 3):
        light("POINT", (x, 10.6 if False else 0.0 + 10.6 * 0, 1.15), 0, size=0.1)  # placeholders (no energy)
    for i, a in enumerate((60, 90, 120)):
        s = light("SPOT", (math.cos(math.radians(a)) * 2, -10, 12), 3200, (1.0, 0.92, 0.78), spot=math.radians(50))
        aim(s, (math.cos(math.radians(a)) * 7, math.sin(math.radians(a)) * 7, 2))
    key = light("SPOT", (0, -6, 9), 2200, (1.0, 0.95, 0.85), spot=math.radians(18))
    aim(key, (0, 2, 2))
    light("AREA", (0, 6, 10), 500, (1.0, 0.85, 0.7), size=10, rot=(0, 0, 0))
    light("POINT", (0, -12, 6), 1500, (0.7, 0.75, 1.0), size=4)
    anchor("SPAWN", (0, -11, 0), rotz=0)
    anchor("SCREEN", (0, 11.9, 6.5), rotz=math.pi)


# ------------------------------------------------------------------ THE READING ROOM (tiered walnut cases, painted vault, rug)
def shelf_wall(prefix, x0, x1, y, z0, z1, rows, facing, group="cases", seed=0):
    """A run of bookcases with books along a wall from x0..x1 at depth y (facing +1 = books face +Y)."""
    import random
    rnd = random.Random(seed)
    w, d = x1 - x0, 0.45
    box(f"{prefix}_back", (w, 0.06, z1 - z0), ((x0 + x1) / 2, y - facing * d / 2, (z0 + z1) / 2), group, "walnut")
    nbays = max(1, int(w / 1.2))
    for b in range(nbays + 1):
        x = x0 + b * w / nbays
        box(f"{prefix}_post_{b}", (0.09, d, z1 - z0), (x, y, (z0 + z1) / 2), group, "walnut")
    for r in range(rows + 1):
        z = z0 + r * (z1 - z0) / rows
        box(f"{prefix}_shelf_{r}", (w, d, 0.05), ((x0 + x1) / 2, y, z), group, "walnut")
    # books: rows of thin boxes in three bindings, with gaps
    hrow = (z1 - z0) / rows
    for r in range(rows):
        z = z0 + r * hrow + 0.03
        x = x0 + 0.06
        while x < x1 - 0.1:
            bw = rnd.uniform(0.035, 0.07); bh = hrow * rnd.uniform(0.62, 0.86)
            if rnd.random() < 0.05:
                x += 0.12; continue
            box(f"{prefix}_bk_{r}_{int(x*1000)}", (bw, d * 0.8, bh), (x + bw / 2, y + facing * 0.02, z + bh / 2), "books", rnd.choice(["books_a", "books_b", "books_c"]))
            x += bw + 0.004


def build_reading():
    L, W, H = 16.0, 11.0, 12.0          # room along X, width along Y
    box("floor", (L, W, 0.1), (0, 0, -0.05), "floor", "oak")
    box("rug", (9, 5.2, 0.02), (0, 0, 0.01), "floor", "rug")
    box("rug_border", (9.5, 5.7, 0.015), (0, 0, 0.005), "floor", "fresco_gold")
    # three tiers of cases on the long walls, two on the end wall, balconies with brass rails
    tiers = [(0.0, 3.4), (3.7, 6.9), (7.2, 10.2)]
    for side in (-1, 1):
        y = side * (W / 2 - 0.3)
        for t, (z0, z1) in enumerate(tiers):
            shelf_wall(f"case_{side}_{t}", -L / 2 + 0.4, L / 2 - 0.4, y, z0 + 0.1, z1, 5, -side, seed=t * 10 + side)
            if t:
                box(f"balc_{side}_{t}", (L - 0.6, 1.0, 0.12), (0, y - side * 0.75, z0 - 0.05), "balcony", "walnut")
                box(f"rail_{side}_{t}", (L - 0.6, 0.05, 0.05), (0, y - side * 1.22, z0 + 1.0), "rails", "brass")
                for i in range(40):
                    box(f"bal_{side}_{t}_{i}", (0.03, 0.03, 1.0), (-L / 2 + 0.5 + i * (L - 1) / 39, y - side * 1.22, z0 + 0.5), "rails", "brass")
    for t, (z0, z1) in enumerate(tiers[:2]):
        shelf_wall(f"case_end_{t}", -W / 2 + 0.8, W / 2 - 0.8, 0, z0 + 0.1, z1, 5, 1, seed=99 + t)
        bpy.context.view_layer.update()
    # rotate the end-wall cases onto the far wall (x = +L/2)
    for o in list(bpy.data.objects):
        if o.name.startswith("case_end_") and o.type == "MESH":
            x, y, z = o.location
            o.location = (L / 2 - 0.3 + (y * 0), x, z)
            o.rotation_euler[2] = math.pi / 2
            o.location = (L / 2 - 0.3 - (o.location[0] - 0) * 0, x, z)
    # near wall: tapestry, fireplace and the doorway back to the Great Hall
    box("near_wall", (0.3, W, H), (-L / 2, 0, H / 2), "walls", "plaster")
    box("tapestry", (0.05, 4.0, 3.0), (-L / 2 + 0.2, -3.0, 4.4), "walls", "tapestry")
    box("fire_surround", (0.5, 2.4, 2.2), (-L / 2 + 0.35, 3.0, 1.1), "walls", "marble")
    box("fire_glow", (0.05, 1.2, 0.8), (-L / 2 + 0.62, 3.0, 0.5), "glow", "glow")
    box("door_frame", (0.4, 2.6, 3.6), (-L / 2 + 0.25, 0, 1.8), "trim", "gold")
    box("door_glow", (0.05, 2.0, 3.2), (-L / 2 + 0.47, 0, 1.6), "glowblue", "glowblue")
    # far wall top + side walls behind the cases
    for side in (-1, 1):
        box(f"side_wall_{side}", (L, 0.2, H), (0, side * W / 2, H / 2), "walls", "plaster")
    box("far_wall", (0.2, W, H), (L / 2, 0, H / 2), "walls", "plaster")
    # painted vault: a barrel of coffers in alternating fresco colours with gilt ribs
    bm = bmesh.new()
    seg, rows = 18, 10
    grid = []
    for j in range(rows + 1):
        x = -L / 2 + j * L / rows
        grid.append([bm.verts.new((x, -W / 2 * math.cos(i / seg * math.pi), 10.2 + 1.7 * math.sin(i / seg * math.pi))) for i in range(seg + 1)])
    faces = []
    for j in range(rows):
        for i in range(seg):
            faces.append(bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1])))
    res = bmesh.ops.inset_individual(bm, faces=faces, thickness=0.12, depth=-0.12)
    o = mesh_from_bm("vault", bm)
    for m in ("fresco_blue", "fresco_gold", "fresco_rose", "gold"):
        o.data.materials.append(M[m])
    for p in o.data.polygons:
        c = p.center
        cell = (int((c.x + L / 2) / (L / rows)) + int((math.atan2(c.z - 10.2, -c.y) / math.pi) * seg)) % 3
        p.material_index = 3 if abs(p.normal.z) < 0.2 and False else cell
    GROUPS.setdefault("vault", []).append(o)
    # display table with glass top in the middle
    box("table", (3.4, 1.2, 0.85), (0, 0, 0.43), "furniture", "walnut")
    box("table_glass", (3.2, 1.0, 0.04), (0, 0, 0.9), "furniture", "glass")
    anchor("TABLE", (0, 0, 0.95), rotz=0)
    anchor("SPAWN", (-L / 2 + 2.2, 0, 0), rotz=-math.pi / 2)
    anchor("DOOR_BACK", (-L / 2 + 0.5, 0, 0), rotz=-math.pi / 2)
    # case anchors for live books: one per bay on the ground tier of each long wall
    k = 0
    for side in (-1, 1):
        for b in range(12):
            x = -L / 2 + 1.0 + b * (L - 2) / 11
            anchor(f"CASE_{k:02d}", (x, side * (W / 2 - 0.55), 0), rotz=(0 if side < 0 else math.pi))
            k += 1
    # lighting: warm chandeliers + window-like fill from the vault + fire
    for x in (-4.5, 0, 4.5):
        cyl(f"chand_{x}", 0.7, 0.12, 20, (x, 0, 8.6), 0.4, "trim", "brass")
        for i in range(6):
            a = i / 6 * math.tau
            cyl(f"bulb_{x}_{i}", 0.06, 0.12, 8, (x + math.cos(a) * 0.6, math.sin(a) * 0.6, 8.72), 0.04, "glow", "glow")
        light("POINT", (x, 0, 8.2), 160, size=0.8)
    light("AREA", (0, 0, 11.5), 260, (1.0, 0.9, 0.75), size=8)
    light("POINT", (-L / 2 + 1.2, 3.0, 0.8), 70, (1.0, 0.55, 0.25), size=0.5)
    for side in (-1, 1):
        for x in (-5, 0, 5):
            light("POINT", (x, side * (W / 2 - 2.2), 5.4), 45, size=0.5)


# ------------------------------------------------------------------ THE ARCHIVE STAIR (grand staircase, mezzanine, lanterns, ladders)
def build_stair():
    L, W, H = 18.0, 12.0, 11.0
    box("floor", (L, W, 0.1), (0, 0, -0.05), "floor", "oak")
    for side in (-1, 1):
        box(f"wall_{side}", (L, 0.2, H), (0, side * W / 2, H / 2), "walls", "royal")
    box("far_wall", (0.2, W, H), (L / 2, 0, H / 2), "walls", "royal")
    box("near_wall", (0.2, W, H), (-L / 2, 0, H / 2), "walls", "royal")
    # tall shelves on both long walls, ground and mezzanine levels
    for side in (-1, 1):
        y = side * (W / 2 - 0.3)
        shelf_wall(f"low_{side}", -L / 2 + 0.6, L / 2 - 0.6, y, 0.1, 4.2, 6, -side, seed=40 + side)
        shelf_wall(f"high_{side}", -L / 2 + 0.6, L / 2 - 0.6, y, 4.9, 9.6, 6, -side, seed=60 + side)
        box(f"mezz_{side}", (L - 0.4, 2.0, 0.2), (0, y - side * 1.1, 4.6), "mezzanine", "walnut")
        box(f"mezz_rail_{side}", (L - 0.4, 0.08, 0.08), (0, y - side * 2.05, 5.6), "rails", "walnut")
        for i in range(30):
            box(f"mezz_bal_{side}_{i}", (0.06, 0.06, 1.0), (-L / 2 + 0.4 + i * (L - 0.8) / 29, y - side * 2.05, 5.1), "rails", "walnut")
        for x in (-6, 0, 6):                       # rolling ladders
            ln = f"ladder_{side}_{x}"
            for r in (-0.22, 0.22):
                o = box(f"{ln}_rail_{r}", (0.05, 0.05, 4.6), (x + r, y - side * 0.5, 2.2), "ladders", "oak")
                o.rotation_euler[0] = side * 0.18
            for k in range(12):
                o = box(f"{ln}_rung_{k}", (0.44, 0.04, 0.04), (x, y - side * (0.5 - 0.04 * (k - 6) * 0.18 * 2), 0.3 + k * 0.36), "ladders", "oak")
    # grand staircase at the far end, rising to a landing and the mezzanines
    steps = 18
    for k in range(steps):
        box(f"step_{k}", (0.42, 3.4, 0.25), (L / 2 - 6.4 + k * 0.32, 0, 0.125 + k * 0.255), "stairs", "walnut")
    box("landing", (2.2, W - 0.4, 0.25), (L / 2 - 1.2, 0, 4.6), "stairs", "walnut")
    for side in (-1, 1):
        for k in range(0, steps, 2):
            box(f"stair_bal_{side}_{k}", (0.07, 0.07, 1.0), (L / 2 - 6.4 + k * 0.32, side * 1.75, 0.6 + k * 0.255), "rails", "oak")
        o = box(f"stair_rail_{side}", (6.2, 0.1, 0.1), (L / 2 - 3.6, side * 1.75, 3.35), "rails", "walnut")
        o.rotation_euler[1] = -math.atan2(0.255, 0.32)
    # tall window at the far wall top, cool daylight
    box("window", (0.05, 2.4, 4.0), (L / 2 - 0.12, 0, 7.6), "window", "skylight")
    # wooden ceiling with beams
    box("ceiling", (L, W, 0.2), (0, 0, H), "ceiling", "walnut")
    for i in range(9):
        box(f"beam_{i}", (0.35, W, 0.45), (-L / 2 + 1 + i * (L - 2) / 8, 0, H - 0.3), "ceiling", "oak")
    # desk with lamp, owl-free; lanterns hanging
    box("desk", (2.4, 1.0, 0.9), (-4, -3.4, 0.45), "furniture", "walnut")
    cyl("lamp_shade", 0.3, 0.35, 20, (-3.2, -3.4, 1.35), 0.18, "glow", "glow")
    for x in (-5, 0, 5):
        cyl(f"lantern_{x}", 0.22, 0.5, 8, (x, 0, 7.4), 0.22, "glow", "glow")
        box(f"lantern_chain_{x}", (0.02, 0.02, 3.2), (x, 0, 9.3), "trim", "brass")
        light("POINT", (x, 0, 7.2), 120, (1.0, 0.75, 0.45), size=0.4)
    light("AREA", (L / 2 - 1.0, 0, 7.6), 300, (0.6, 0.75, 1.0), size=3, rot=(0, -math.pi / 2, 0))
    light("POINT", (-3.2, -3.4, 1.6), 25, (1.0, 0.8, 0.5), size=0.2)
    light("AREA", (0, 0, 10.4), 120, (1.0, 0.85, 0.7), size=10)
    box("door_frame", (0.4, 2.6, 3.6), (-L / 2 + 0.25, 0, 1.8), "trim", "brass")
    box("door_glow", (0.05, 2.0, 3.2), (-L / 2 + 0.47, 0, 1.6), "glow", "glow")
    anchor("SPAWN", (-L / 2 + 2.2, 0, 0), rotz=-math.pi / 2)
    anchor("DOOR_BACK", (-L / 2 + 0.5, 0, 0), rotz=-math.pi / 2)
    # the thread: stations along the floor and up the stair (a story you walk through)
    for k in range(12):
        if k < 6:
            p = (-L / 2 + 4.3 + k * 1.3, (-1) ** k * 1.6, 0)
        else:
            j = (k - 6) * 3
            p = (L / 2 - 6.2 + j * 0.32, 0.9 * (-1) ** k, j * 0.255 + 0.25)
        anchor(f"STATION_{k:02d}", p, rotz=-math.pi / 2)


# ------------------------------------------------------------------ bake
def bake_and_export(name):
    if A.unreal:
        name += "_ue"
        scene.cycles.samples = 1
    scene.cycles.bake_type = "DIFFUSE" if A.unreal else "COMBINED"
    bake = scene.render.bake
    bake.margin = 4
    for g, objs in GROUPS.items():
        if not objs:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        o.name = f"{name}_{g}"
        if g in ("glow", "sky", "glowblue", "window"):                     # emissive: keep as unbaked bright colour
            o["emissive"] = 1
            continue
        if A.nobake:
            continue
        # lightmap UVs
        me = o.data
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name="UVMap")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        res = A.res * (2 if g in ("floor", "walls", "dome") and A.res >= 2048 else 1)
        img = bpy.data.images.new(f"{name}_{g}_bake", res, res)
        for m in o.data.materials:
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = img
            m.node_tree.nodes.active = n
        log("bake", g, f"{res}px", f"{len(o.data.polygons)} faces")
        if A.unreal:
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
        else:
            bpy.ops.object.bake(type="COMBINED")
        img.filepath_raw = os.path.join(A.out, f"{name}_{g}.png")
        img.file_format = "PNG"
        img.save()
        try:                                   # light denoise of the bake (median), then reload
            from PIL import Image, ImageFilter
            Image.open(img.filepath_raw).filter(ImageFilter.MedianFilter(3)).save(img.filepath_raw)
            img.reload()
        except Exception as e:
            log("no PIL denoise:", e)
        # replace materials by a single unlit-ready material carrying the baked texture
        bm = bpy.data.materials.new(f"{name}_{g}_baked")
        bm.use_nodes = True
        nt = bm.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        nt.links.new(tx.outputs["Color"], bsdf.inputs["Base Color"])
        if A.unreal:                               # keep the original feel for Unreal's lighting
            src = M.get(g) or next(iter(M.values()))
            bsdf.inputs["Roughness"].default_value = {"trim": 0.28, "floor": 0.22, "drapes": 0.9, "pilasters": 0.3}.get(g, 0.5)
            bsdf.inputs["Metallic"].default_value = 1.0 if g in ("trim", "pilasters") else 0.0
        o.data.materials.clear()
        o.data.materials.append(bm)
        o["baked"] = 1
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(A.out, f"{name}_lit.blend"))
    # web: remove lights (lighting lives in the textures); Unreal: keep them as glTF punctual lights
    if not A.unreal:
        for ob in list(bpy.data.objects):
            if ob.type == "LIGHT":
                bpy.data.objects.remove(ob)
    path = os.path.join(A.out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_extras=True, export_image_format="JPEG",
                              export_jpeg_quality=85, export_apply=True, export_lights=A.unreal, export_cameras=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(A.out, f"{name}.blend"))
    log("exported", path, f"{os.path.getsize(path) / 1e6:.1f} MB")


{"hall": build_hall, "presidents": build_presidents, "reading": build_reading, "stair": build_stair}[A.scene]()
log("built", A.scene, sum(len(v) for v in GROUPS.values()), "objects in", len(GROUPS), "bake groups")
bake_and_export({"hall": "great_hall", "presidents": "presidents_hall", "reading": "reading_room", "stair": "archive_stair"}[A.scene])
