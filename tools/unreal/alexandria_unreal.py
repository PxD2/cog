"""Alexandria in Unreal — builds the Great Hall and the Hall of Presidents levels in the ALEXANDERIA project (UE 5.7, VR Template).

Run inside the Unreal Editor (Python plugin on):  Tools → Execute Python Script → this file
or in the Output Log's Python console:            exec(open(r"C:\\Users\\pxdis\\PxD2\\alexandria\\unreal\\alexandria_unreal.py").read())

What it does
  1. Imports the Blender sets made for Unreal (surface colour + real lights): sets/great_hall_ue.glb, sets/presidents_hall_ue.glb
     into /Game/Alexandria/Sets/... with the Interchange glTF importer, as whole scenes (meshes, materials, lights, anchors).
  2. Makes a level for each: L_GreatHall and L_HallOfPresidents, with Lumen GI + reflections, a sky light, exponential
     height fog (volumetric), a post-process volume (filmic, bloom, mild lens), and the VR Template pawn at SPAWN.
  3. Adds a NavMesh bounds volume so the VR Template's teleport works on the floors.
Anchors from Blender (NICHE_k, ORB, P01..P47, LECTERN, SCREEN) come in as empty actors with the same names, ready for
Blueprints (books, presidents, speech panels). Nothing here is downloaded; it only reads the .glb files on this PC.
"""
import os
import unreal

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\Users\pxdis\PxD2\alexandria\unreal"
SETS = os.path.normpath(os.path.join(ROOT, "..", "sets"))
SCENES = [("great_hall_ue.glb", "/Game/Alexandria/Sets/GreatHall", "/Game/Alexandria/L_GreatHall"),
          ("presidents_hall_ue.glb", "/Game/Alexandria/Sets/HallOfPresidents", "/Game/Alexandria/L_HallOfPresidents")]
VR_PAWN = "/Game/VRTemplate/Blueprints/VRPawn.VRPawn_C"
log = unreal.log


def import_scene(glb, dest):
    src = os.path.join(SETS, glb)
    if not os.path.exists(src):
        unreal.log_error(f"missing {src} — copy the sets folder next to this script")
        return False
    try:                                            # UE 5.3+: import the whole scene into the open level
        mgr = unreal.InterchangeManager.get_interchange_manager_scripted()
        source = unreal.InterchangeManager.create_source_data(src)
        params = unreal.ImportAssetParameters()
        params.is_automated = True
        mgr.import_scene(dest, source, params)
        log(f"Interchange scene import: {glb}")
        return True
    except Exception as e:                          # fallback: assets only (place them by hand)
        unreal.log_warning(f"scene import failed ({e}); importing assets only")
        task = unreal.AssetImportTask()
        task.filename, task.destination_path, task.automated, task.save = src, dest, True, True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        return True


def add(cls, loc=(0, 0, 0), rot=(0, 0, 0)):
    return unreal.EditorLevelLibrary.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))


def dress_level():
    sky = add(unreal.SkyLight)
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_intensity(0.6)
    fog = add(unreal.ExponentialHeightFog)
    fc = fog.component
    fc.set_editor_property("volumetric_fog", True)
    fc.set_editor_property("fog_density", 0.012)
    fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.08, 0.07, 0.06, 1))
    ppv = add(unreal.PostProcessVolume)
    ppv.set_editor_property("unbound", True)
    s = ppv.settings
    for k, v in (("override_dynamic_global_illumination_method", True), ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
                 ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
                 ("override_bloom_intensity", True), ("bloom_intensity", 0.8),
                 ("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                 ("override_auto_exposure_bias", True), ("auto_exposure_bias", 11.0),
                 ("override_vignette_intensity", True), ("vignette_intensity", 0.35),
                 ("override_film_grain_intensity", True), ("film_grain_intensity", 0.08)):
        try:
            s.set_editor_property(k, v)
        except Exception:
            pass
    ppv.set_editor_property("settings", s)
    nav = add(unreal.NavMeshBoundsVolume, (0, 0, 200))
    nav.set_actor_scale3d(unreal.Vector(40, 40, 8))


def spawn_at(name):
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if a.get_actor_label() == name or a.get_name() == name:
            return a.get_actor_location(), a.get_actor_rotation()
    return unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)


def build():
    for glb, dest, level in SCENES:
        unreal.EditorLevelLibrary.new_level(level)
        if not import_scene(glb, dest):
            continue
        dress_level()
        loc, rot = spawn_at("SPAWN")
        pawn_cls = unreal.EditorAssetLibrary.load_blueprint_class(VR_PAWN.rsplit(".", 1)[0]) if unreal.EditorAssetLibrary.does_asset_exist(VR_PAWN.rsplit(".", 1)[0]) else None
        if pawn_cls:
            p = unreal.EditorLevelLibrary.spawn_actor_from_class(pawn_cls, loc, rot)
            p.set_editor_property("auto_possess_player", unreal.AutoReceiveInput.PLAYER0)
        else:
            add(unreal.PlayerStart, (loc.x, loc.y, loc.z + 100))
        unreal.EditorLevelLibrary.save_current_level()
        log(f"built {level}")
    unreal.EditorDialog.show_message("Alexandria", "Built L_GreatHall and L_HallOfPresidents in /Game/Alexandria.\nBuild → Build Paths for teleport, then VR Preview.", unreal.AppMsgType.OK)


build()
