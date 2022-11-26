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
from random import getrandbits
from bpy.types import (
    PropertyGroup,
    Operator,
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
from math import pi, sqrt, log2



# Addon Utils

class Utils:

    @staticmethod
    def renderToPath(context, target_filepath :str, target_filename: str):
        """ Renders scene onto designated path and filename """
        curr_filepath = str(context.scene.render.filepath)
        target_filepath = os.path.join(target_filepath, target_filename)
        context.scene.render.filepath = target_filepath
        bpy.ops.render.render(write_still=True)
        context.scene.render.filepath = curr_filepath

    @staticmethod
    def mkdir(path: str):
        """ Creates new directory if said directory does not exist """
        if not os.path.isdir(path):
            os.mkdir(path)

    @staticmethod
    def assertObjectMode(context):
        if context.active_object and not context.active_object.mode == 'OBJECT':
            print('WARNING: Reverting {context.active_object.mode} into OBJECT mode on object {context.active_object.name}`.')
            bpy.ops.object.mode_set(mode='OBJECT')


class ObjectUtils:

    # this string configuration ensures object always stays on the bottom of object list on the outliner (assuming ascending sort)
    addon_object_default_prefix = '||sprshtt_addon_object_' 

    @staticmethod
    def sGetDefaultPrefix(mid:str = '') -> str:
        if mid:
            return ObjectUtils.addon_object_default_prefix + mid + '_'
        return str(ObjectUtils.addon_object_default_prefix)

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
                ls.append(bpy.data.objects[item])
        return ls

    @staticmethod
    def deleteObjectsFromScene(objs: list):
        """ Deletes objects data from scene context """
        if objs:
            for obj in objs:
                bpy.data.objects.remove(obj, do_unlink=True) 
            # scene_copy = bpy.context.copy()
            # scene_copy['selected_objects'] = objs
            # bpy.ops.object.delete(scene_copy)

    @staticmethod
    def sGenerateUniqueObjectName(mid: str = '') -> str:
        """ Generates unique object name with predefined prefix """
        while True:
            name = ObjectUtils.sGetDefaultPrefix(mid)
            name += '%08x' % getrandbits(32)
            if not ObjectUtils.bBObjectsHasPrefix(name):
                return name

    @staticmethod
    def uCalcObjectBboxDimension(obj: BObject):
        rot = obj.rotation_euler.copy()
        dim = obj.dimensions.to_3d()
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        x, y, z = [ [ c[i] for c in corners ] for i in range(3) ]
        fcenter = lambda x: ( max(x) + min(x) ) / 2
        center = [ fcenter(axis) for axis in [x,y,z] ]
        return Vector(center), dim, rot

    @staticmethod
    def uMoveObjectAlongAxis(obj: BObject, dest: float = 0.0, axis=(0,0,1)):
        axis = Vector(axis)
        dest = axis * dest
        mat_inv = obj.matrix_world.copy()
        mat_inv.invert()
        obj.location += dest @ mat_inv
        return obj



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
        default=False,
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
        name='Camera Azimuth', 
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
        name='Target'
        )

    collection_target_cameras: PointerProperty(
        type=bpy.types.Object, 
        poll=lambda s, x: x.type == 'CAMERA',
        name='Camera'
        )
    
    # ????
    private_str_target_obj_name: StringProperty()
    private_float_target_obj_dimension: FloatVectorProperty()


# Addon Operators

class SPRSHTT_Opr_CreateHelperObject(Operator):
    bl_idname = "object.sprshtt_create_helper_object"
    bl_label = "Create Helper Object on Target Object"

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties

        target_object = addon_prop.collection_target_objects
        if not target_object:
            return {'CANCELLED'}

        Utils.assertObjectMode(context)

        coord, dim, rot = ObjectUtils.uCalcObjectBboxDimension(target_object)
        # coord : Vector
        # rot   : Euler
        # dim   : Vector

        ObjectUtils.deleteObjectsFromScene(ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix()))

        bpy.ops.object.empty_add(type='SINGLE_ARROW', radius=dim.length, location=coord, rotation=rot)
        obj = bpy.context.selected_objects[0]
        obj.name = ObjectUtils.sGenerateUniqueObjectName('axis-helper-arrow')
        obj.empty_display_size = dim.length
        if abs(dim.z) <= 1: obj.empty_display_size = 1

        rot.rotate_axis('X', pi/2)

        bpy.ops.object.empty_add(type='CIRCLE', radius=dim.length, location=coord, rotation=rot)
        obj = bpy.context.selected_objects[0]
        obj.name = ObjectUtils.sGenerateUniqueObjectName('axis-helper-circle')
        obj.empty_display_size = dim.length
        obj.show_axis = True
        if abs(dim.z) <= 1: obj.empty_display_size = 1

        bpy.ops.object.select_all(action='DESELECT')

        if target_object:
            target_object.select_set(True)
            addon_prop.private_str_target_obj_name = target_object.name
        addon_prop.private_float_target_obj_dimension = dim

        return {'FINISHED'}

class SPRSHTT_Opr_CreateCamera(Operator):
    """ Create custom camera """
    bl_idname = 'object.sprshtt_create_camera'
    bl_label = "Create Custom Camera"

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties
        objects = scene.objects
        ops_object = bpy.ops.object # cursed bypass
        target_object = addon_prop.collection_target_objects

        is_helper_already_exist = False
        if ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')) and \
            ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-circle')):
            is_helper_already_exist = True
        else:
            ops_object.sprshtt_create_helper_object('EXEC_DEFAULT') # recreate helper objects

        if not target_object:
            return {'CANCELLED'}

        if addon_prop.bool_existing_camera:
            context.scene.camera = ObjectUtils.qAllBObjectsWithPrefix('Camera')[0]
            return {'FINISHED'}

        # program begins
        ObjectUtils.deleteObjectsFromScene(ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('camera')))
        helper_object = ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow'))[0]

        camera_inclination = addon_prop.float_camera_inclination_offset
        camera_azimuth = addon_prop.float_camera_azimuth_offset
        camera_offset = addon_prop.float_distance_offset

        if addon_prop.bool_auto_camera_offset:
            _, dim, _  = ObjectUtils.uCalcObjectBboxDimension(helper_object)
            camera_offset = helper_object.empty_display_size + log2(helper_object.empty_display_size + 1) * 8

        loc, _, rot = ObjectUtils.uCalcObjectBboxDimension(helper_object)

        bpy.ops.object.camera_add(location=loc, rotation=rot)

        obj = context.selected_objects[0]
        obj.name = ObjectUtils.sGenerateUniqueObjectName('camera')
        obj.data.type = addon_prop.enum_camera_type
        obj.data.show_sensor = True
        obj.data.show_limits = True
        ObjectUtils.uMoveObjectAlongAxis(obj, camera_offset, axis=(0,-1,0))
        obj.rotation_euler.rotate_axis('X', pi/2)
        context.scene.camera = obj


        if not is_helper_already_exist:
            # delete helper objects from recreation
            for t in ['axis-helper-arrow', 'axis-helper-circle']:
                ObjectUtils.deleteObjectsFromScene(ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix(t)))

        return {'FINISHED'}


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
        ## ColGroup 0
        subcol = col.column()
        subcol.enabled = bool(addon_prop.collection_target_objects) 
        subcol.operator('object.sprshtt_create_helper_object', text='Spawn Target Helper')
        col.prop(addon_prop, 'bool_existing_camera')
        ## ColGroup 1
        subcol = col.column()
        subcol.enabled = addon_prop.bool_existing_camera 
        subcol.prop(addon_prop, 'collection_target_cameras')
        ## ColGroup 2
        subcol = col.column()
        subcol.enabled = not addon_prop.bool_existing_camera
        subcol.prop(addon_prop, 'enum_camera_type')
        subcol.prop(addon_prop, 'float_camera_inclination_offset')
        subcol.prop(addon_prop, 'float_camera_azimuth_offset')
        subcol.prop(addon_prop, 'bool_auto_camera_offset')
        subcol.prop(addon_prop, 'float_distance_offset')
        subcol.prop(addon_prop, 'fvec_camera_target_pos_offset' )
        subcol.prop(addon_prop, 'fvec_camera_target_rot_offset' )


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
    SPRSHTT_Opr_CreateHelperObject,
    SPRSHTT_Opr_CreateCamera,
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

    
    