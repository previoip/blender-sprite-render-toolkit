import bpy


bl_info = {
    "name": "Sprite Sheet Render Toolkit",
    "author": "Previo Prakasa (github.com/previoip)",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Properties > Render",
    "description": "Render toolkit using camera manipulation for generating 2D sprite sheet from 3D assets.",
    "warning": "This is an experimental project and should not be used in any form of production (as of today).",
}

from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    StringProperty,
    EnumProperty,
    PointerProperty
)

from bpy.types import PropertyGroup

class SPSPRT_PropertyGroup(PropertyGroup):

    str_export_folder: StringProperty(
        name='Export Folder', 
        description = 'Export subfolder name',
        default='/export'
        )

    str_file_suffix: StringProperty(
        name='Suffix', 
        description = 'Generated images suffix',
        default=''
        )

    enable_post_processing: BoolProperty(
        name='Use internal mask post processing',
        description = 'Use external script to process mask-map and colliders',
        )

    int_frame_skip: IntProperty(
        name='Frame-skip', 
        description = 'Skips frame if jump number of frames for rendering (used to check render result)',
        default=10, 
        min=1, 
        max=1000
        )

    enable_frame_skip: BoolProperty(
        name='Enable Frame-skip',
        description = 'Use frame skipping for rendering animated object',
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

    float_camera_inclination: FloatProperty(
        name='Camera Inclination', 
        description = 'Camera inclination to the normal plane of target object.',
        default=57.3, 
        min=-360, 
        max=360, 
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

    float_angle_offset: FloatProperty(
        name='Offset Angle', 
        description = 'Camera angle offset to target reference',
        default=0, 
        min=-360, 
        max=360, 
        precision=2,
        subtype='ANGLE'
        )

    float_distance_offset: FloatProperty(
        name='Offset Distance', 
        description = 'Camera distance offset to target reference',
        min=0,
        default=20, 
        max=1000
        )
        
    enable_auto_camera_offset: BoolProperty(
        name='Auto Offset', 
        description = 'Automatically set distance by object bounding-box size',
        default=False, 
        )

    enable_auto_camera_scale: BoolProperty(
        name='Auto Camera Scale', 
        description = 'Automatically set camera scale by object bounding-box size',
        default=False, 
        )

    range_camera_movement_rotation: FloatProperty(
        name='Pivot Angle', 
        description = 'Adjust camera initial position',
        default=45, 
        min=-180, 
        max=180, 
        precision=2,
        subtype='ANGLE'
        )


class SPSPRT_PT_render_panel(bpy.types.Panel):
    bl_label        = 'SPSPRT Toolkit'
    bl_idname       = 'SCENE_PT_layout'
    bl_space_type   = 'PROPERTIES'
    bl_region_type  = 'WINDOW'
    bl_context      = 'render'
    bl_options      = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        row = col.row()
        row.prop(context.scene.spsprt_properties, 'str_export_folder')  

classes = (SPSPRT_PT_render_panel, SPSPRT_PropertyGroup)

def register():

    for cl in classes:
        bpy.utils.register_class(cl)
    bpy.types.Scene.spsprt_properties = PointerProperty(type=SPSPRT_PropertyGroup)
    unregister()

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    delattr(bpy.types.Scene, 'spsprt_properties')

if __name__ == '__main__':
    import os

    register()

    
    