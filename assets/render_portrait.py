"""Render a posed model for the Studio portrait cropper in a fresh Blender process."""
import argparse
from math import cos, radians, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def load_model(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix.lower() == ".geom":
        import addon_utils
        addon = addon_utils.enable("Time_Stranger_Importer", default_set=False)
        if addon is None:
            raise ValueError("Install the Time Stranger Importer in this Blender version to capture a GEOM.")
        from Time_Stranger_Importer.src.geom import import_geom
        collection = import_geom(bpy.context, str(path))
        objects = list(collection.all_objects)
    else:
        result = bpy.ops.import_scene.gltf(filepath=str(path), import_pack_images=True)
        if result != {"FINISHED"}:
            raise ValueError("Blender could not import the selected model.")
        objects = list(bpy.context.scene.objects)

    # glTF can contain multiple staged actions and decorative bone-shape meshes.
    custom_shapes = {bone.custom_shape for obj in objects if obj.type == 'ARMATURE'
                     for bone in obj.pose.bones if bone.custom_shape}
    meshes = []
    for obj in objects:
        animation = obj.animation_data
        if animation:
            strips = {track.name.casefold(): strip for track in animation.nla_tracks
                      for strip in track.strips if strip.action}
            idle = next((strips[name] for name in ('stand', 'idle', path.stem.lower() + '_bn01')
                         if name in strips), None)
            if idle:
                for track in animation.nla_tracks:
                    track.mute = True
                animation.action = idle.action
                animation.action_slot = idle.action_slot
        if obj.type == 'MESH':
            materials = [slot.material for slot in obj.material_slots if slot.material]
            helper = obj in custom_shapes or (path.suffix.lower() == '.geom' and
                obj.name.lower().endswith('_effect')) or (materials and all(
                m.name.lower().startswith('mtr_line') or m.name.lower().endswith('_effect')
                for m in materials))
            if helper:
                obj.hide_render = True
            elif not obj.hide_render and obj.visible_get():
                meshes.append(obj)
    if not meshes:
        raise ValueError("The selected model has no visible meshes to photograph.")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    return meshes


def surface_materials(meshes):
    """Use the body texture and soft studio lighting, including native GEOM texture groups."""
    materials = {slot.material for mesh in meshes for slot in mesh.material_slots if slot.material}
    for material in materials:
        if not material.use_nodes:
            continue
        tree = material.node_tree
        native_image = next((node.image for group in tree.nodes if group.type == 'GROUP' and group.node_tree
                             for node in group.node_tree.nodes
                             if node.type == 'TEX_IMAGE' and node.label in {
                                 'DSTS-DiffuseColor', 'DSTS-ColorSampler'} and node.image), None)
        if native_image:
            texture = tree.nodes.new('ShaderNodeTexImage')
            texture.image = native_image
            surface = tree.nodes.new('ShaderNodeBsdfPrincipled')
            surface.inputs['Roughness'].default_value = 1.0
            tree.links.new(texture.outputs['Color'], surface.inputs['Base Color'])
            output = next(node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
            tree.links.new(surface.outputs[0], output.inputs['Surface'])


def render(model, output, yaw, pitch, crop, pixels):
    meshes = load_model(model)
    surface_materials(meshes)
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new("Portrait studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.65
    azimuth, elevation = radians(yaw), radians(pitch)
    direction = Vector((sin(azimuth)*cos(elevation), -cos(azimuth)*cos(elevation), sin(elevation)))
    rotation = (-direction).to_track_quat('-Z', 'Y')
    right, up = rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0))

    depsgraph = bpy.context.evaluated_depsgraph_get()
    # Measured vertices keep asymmetric wings, horns, and tails inside the full view.
    projected = []
    for mesh in meshes:
        obj = mesh.evaluated_get(depsgraph)
        for vertex in obj.data.vertices:
            position = obj.matrix_world @ vertex.co
            projected.append((position.dot(right), position.dot(up), position.dot(direction)))
    x, y, z = zip(*projected)
    size = max(max(x)-min(x), max(y)-min(y), 1e-5)*1.05
    left, top, fraction = crop
    if not (fraction > 0 and 0 <= left <= 1-fraction+1e-6 and 0 <= top <= 1-fraction+1e-6):
        raise ValueError("The crop must fit inside the full view.")
    cx = (max(x)+min(x))/2 + (left+fraction/2-0.5)*size
    cy = (max(y)+min(y))/2 - (top+fraction/2-0.5)*size
    camera = bpy.data.cameras.new("Portrait")
    camera.type, camera.ortho_scale = 'ORTHO', size*fraction
    camera.clip_start = max(size*0.0001, 0.00001)
    camera.clip_end = max(size*10 + max(z)-min(z), 100)
    scene.camera = bpy.data.objects.new("Portrait", camera)
    scene.collection.objects.link(scene.camera)
    scene.camera.location = right*cx + up*cy + direction*(max(z)+size)
    scene.camera.rotation_euler = rotation.to_euler()
    light = bpy.data.lights.new("Soft key", 'SUN')
    light.energy, light.angle = 1.5, radians(28)
    lamp = bpy.data.objects.new("Soft key", light)
    scene.collection.objects.link(lamp)
    lamp.rotation_euler = (-direction + right*0.55 - up*1.3).to_track_quat('-Z', 'Y').to_euler()
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 6
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = scene.render.resolution_y = pixels
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--yaw", type=float, default=50)
    parser.add_argument("--pitch", type=float, default=12)
    parser.add_argument("--crop", type=float, nargs=3, default=(0, 0, 1))
    parser.add_argument("--pixels", type=int, default=768)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    render(args.model, args.output, args.yaw, args.pitch, args.crop, args.pixels)
