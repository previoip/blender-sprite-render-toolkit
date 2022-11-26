bl_info = {
    "name": "Sprite Sheet Render Toolkit",
    "blender": (2, 80, 0),
    "category": "Render",
    "support": "COMMUNITY",
    "author": "Previo Prakasa (github.com/previoip)",
    "version": (0, 0, 1),
    "location": "View3D > Properties > Render",
    "description": "Render toolkit using camera manipulation for generating 2D sprite sheet from 3D assets.",
    "warning": "This is an experimental project and should not be used in any form of production (as of today).",
}

import bpy
import os
from bpy.types import (
    PropertyGroup,
    Object as BObject
)
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    StringProperty,
    EnumProperty,
    PointerProperty
)
from mathutils import Vector, Matrix, Euler
from math import pi, sqrt


# Addon Utils

class utils:

    @staticmethod
    def bBObjectsHasPrefix(prefix: str) -> bool:
        """ Checks if blender data.objects has object with prefix """
        for item in bpy.data.objects.keys():
            if item.startswith(prefix):
                return True
        return False    

    @staticmethod
    def qAllBObjectsWithPrefix(prefix: str) -> list:
        """ Queries and returns all object that has prefix """
        ls = []
        for item in bpy.data.objects.keys():
            if item.startswith(prefix):
                ls.append(item)
        return ls

    @staticmethod
    def deleteObjectsFromScene(objs: list):
        """ Deletes objects data from scene context """
        scene_copy = bpy.context.copy()
        scene_copy['selected_objects'] = objs
        bpy.ops.object.delete(scene_copy)

    @staticmethod
    def renderToPath(context, target_filepath, target_filename):
        """ Renders scene onto designated path and filename """
        curr_filepath = str(context.scene.render.filepath)
        target_filepath = os.path.join(target_filepath, target_filename)
        context.scene.render.filepath = target_filepath
        bpy.ops.render.render(write_still=True)
        context.scene.render.filepath = curr_filepath


# Addon Properties

class SPRSHTT_PropertyGroup(PropertyGroup):

    str_export_folder: StringProperty(
        name='Export Folder', 
        description = 'Export subfolder',
        default='/export'
        )

    str_file_suffix: StringProperty(
        name='Suffix', 
        description = 'Generated images suffix',
        default=''
        )

    bool_post_processing: BoolProperty(
        name='Use internal mask post processing',
        description = 'Use external script to process mask-map and colliders (requires PIL)',
        )

    bool_existing_camera: BoolProperty(
        name='Use Existing Camera',
        description = 'Use existing camera instead of generated from these settings',
        )

    enum_camera_type: EnumProperty(
        name='Type', 
        description = 'Change default camera type',
        items = [
            ("ORTHO", "Orthographic", "", 1),
            ("PERSP", "Perspective", "", 2),
        ],
        default="ORTHO"
        )

    bool_frame_skip: BoolProperty(
        name='Enable Frame-skip',
        description = 'Use frame skipping for rendering animated object',
        )

    int_frame_skip: IntProperty(
        name='Frame-skip', 
        description = 'Skips frame if jump number of frames for rendering (used to check render result)',
        default=10, 
        min=1, 
        max=1000
        )

    float_camera_inclination_offset: FloatProperty(
        name='Camera Inclination', 
        description = 'Camera inclination to the normal plane of target object.',
        default=57.3*pi/180, 
        min=-pi, 
        max=pi, 
        precision=2,
        subtype='ANGLE'
        )

    float_camera_azimuth_offset: FloatProperty(
        name='Offset Angle', 
        description = 'Camera angle offset to target reference',
        default=0, 
        min=-pi,
        max=pi,
        precision=2,
        subtype='ANGLE'
        )

    int_render_increment: IntProperty(
        name='Increment', 
        description = 'Camera n of increment in one render cycle (rotates 360 degrees).',
        default=8, 
        min=1, 
        max=36
        )

    bool_auto_camera_offset: BoolProperty(
        name='Auto Offset', 
        description = 'Automatically set distance by object bounding-box size',
        default=False, 
        )

    float_distance_offset: FloatProperty(
        name='Offset Distance', 
        description = 'Camera distance offset to target reference',
        min=0,
        default=20, 
        max=1000
        )

    bool_auto_camera_scale: BoolProperty(
        name='Auto Camera Scale', 
        description = 'Automatically set camera scale by object bounding-box size',
        default=False, 
        )

    range_camera_movement_rotation: FloatProperty(
        name='Pivot Angle', 
        description = 'Adjust camera initial position',
        default=pi/4, 
        min=-pi, 
        max=pi, 
        precision=2,
        subtype='ANGLE'
        )

    range_camera_movement_rotation: FloatProperty(
        name='Pivot Angle', 
        description = 'Adjust camera initial position',
        default=45, 
        min=-pi, 
        max=pi, 
        precision=2,
        subtype='ANGLE'
        )

    fvec_camera_target_pos_offset: FloatVectorProperty(
        name='Target Position Offset', 
        description='Camera target offset relative to center of mass of target/selected object', 
        default=(0.0, 0.0, 0.0),  
        unit='LENGTH'
        )


    fvec_camera_target_rot_offset: FloatVectorProperty(
        name='Tilt Offset', 
        description='Camera target tilt relative to normal up-direction of target/selected object', 
        default=(0.0, 0.0, 0.0), 
        unit='ROTATION'
        )

    collection_target_objects: PointerProperty(
        type=bpy.types.Object, 
        poll=lambda s, x: x.type == 'MESH',
        name='Object'
        )

    collection_target_cameras: PointerProperty(
        type=bpy.types.Object, 
        poll=lambda s, x: x.type == 'CAMERA',
        name='Camera'
        )

# Addon UIs

class SPRSHTT_Panel_baseProps:
    bl_space_type   = 'PROPERTIES'
    bl_region_type  = 'WINDOW'
    bl_context      = 'render'

class SPRSHTT_PT_render_panel(SPRSHTT_Panel_baseProps, bpy.types.Panel):
    bl_label        = '< Sprite Sheet Toolkit >'
    bl_options      = {'DEFAULT_CLOSED'}

    def draw(self, context):
        pass

class SPRSHTT_PT_render_panel_addon(SPRSHTT_Panel_baseProps, bpy.types.Panel):
    bl_label = "Addon Settings"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene

        col = layout.column()
        col.prop(addon_prop, 'collection_target_objects' )
        col.prop(addon_prop, 'bool_existing_camera')
        ## ColGroup 1
        subcol = col.column()
        subcol.prop(addon_prop, 'collection_target_cameras')
        subcol.enabled = addon_prop.bool_existing_camera 
        ## ColGroup 2
        subcol = col.column()
        subcol.enabled = not addon_prop.bool_existing_camera
        subcol.prop(addon_prop, 'enum_camera_type')
        subcol.prop(addon_prop, 'float_camera_inclination_offset')
        subcol.prop(addon_prop, 'float_camera_azimuth_offset')
        subcol.prop(addon_prop, 'bool_auto_camera_offset')
        subcol.prop(addon_prop, 'float_distance_offset')
        col.prop(addon_prop, 'fvec_camera_target_pos_offset' )
        col.prop(addon_prop, 'fvec_camera_target_rot_offset' )


class SPRSHTT_PT_render_panel_renderer(SPRSHTT_Panel_baseProps, bpy.types.Panel):
    bl_label = "Renderer Settings"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene
        col = layout.column()
        col.prop(addon_prop, 'int_render_increment')
        col.prop(addon_prop, 'bool_frame_skip')
        subcol = col.column()
        subcol.enabled = addon_prop.bool_frame_skip
        subcol.prop(addon_prop, 'int_frame_skip')

class SPRSHTT_PT_render_panel_output(SPRSHTT_Panel_baseProps, bpy.types.Panel):
    bl_label = "Output Preference"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene

        col = layout.column()
        col.prop(addon_prop, 'str_export_folder')
        col.prop(addon_prop, 'str_file_suffix')
        col.prop(addon_prop, 'bool_post_processing')

# Addon Register/Unregister 

classes = (
    SPRSHTT_PT_render_panel,
    SPRSHTT_PT_render_panel_addon,
    SPRSHTT_PT_render_panel_renderer,
    SPRSHTT_PT_render_panel_output, 
    SPRSHTT_PropertyGroup,
)

def register():
    for cl in classes:
        bpy.utils.register_class(cl)
    bpy.types.Scene.sprshtt_properties = PointerProperty(type=SPRSHTT_PropertyGroup)

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    delattr(bpy.types.Scene, 'sprshtt_properties')

if __name__ == '__main__':
    register()

    
    