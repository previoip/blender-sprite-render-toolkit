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
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    StringProperty,
    EnumProperty,
    PointerProperty
)
from math import pi

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
        name='Camera Type', 
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

    fvec_target_object_pos_offset: FloatVectorProperty(
        name='Target Position Offset', 
        description='Camera target offset relative to center of mass of target/selected object', 
        default=(0.0, 0.0, 0.0),  
        unit='LENGTH'
        )


    fvec_target_object_rot_offset: FloatVectorProperty(
        name='Tilt Offset', 
        description='Camera target tilt relative to normal up-direction of target/selected object', 
        default=(0.0, 0.0, 0.0), 
        unit='ROTATION'
        )

    collection_target_object: PointerProperty(
        type=bpy.types.Object, 
        poll=lambda s, x: x.type == 'MESH',
        name='Object'
        )

class SPRSHTT_PT_render_panel(bpy.types.Panel):
    bl_label        = '< Sprite Sheet Toolkit >'
    bl_idname       = 'SCENE_PT_layout'
    bl_space_type   = 'PROPERTIES'
    bl_region_type  = 'WINDOW'
    bl_context      = 'render'
    bl_options      = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene

        box = layout.box()
        box.label(text="Preferences")
        col = box.column()
        col.prop(addon_prop, 'str_export_folder')
        col.prop(addon_prop, 'str_file_suffix')
        col.prop(addon_prop, 'bool_post_processing')

        box = layout.box()
        box.label(text="Target Object Properties")
        col = box.column()
        col.prop(addon_prop, 'collection_target_object' )
        col.prop(addon_prop, 'fvec_target_object_pos_offset' )
        col.prop(addon_prop, 'fvec_target_object_rot_offset' )

        box = layout.box()
        box.label(text="Camera Properties")
        col = box.column()
        col.prop(addon_prop, 'bool_existing_camera')
        col.prop(addon_prop, 'enum_camera_type')
        col.prop(addon_prop, 'float_camera_inclination_offset')
        col.prop(addon_prop, 'float_camera_azimuth_offset')
        col.prop(addon_prop, 'bool_auto_camera_offset')
        col.prop(addon_prop, 'float_distance_offset')
        col.prop(addon_prop, 'bool_auto_camera_scale')


        box = layout.box()
        box.label(text="Renderer Properties")
        col = box.column()
        col.prop(addon_prop, 'int_render_increment')
        col.prop(addon_prop, 'bool_frame_skip')
        col.prop(addon_prop, 'int_frame_skip')


classes = (SPRSHTT_PT_render_panel, SPRSHTT_PropertyGroup)

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

    
    