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
from math import pi, sqrt, log2, isclose



# Addon Utils

class Utils:
    addon_previously_selected = None

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
    def bAssertObjectMode(context, strict=True):
        if context.active_object and not context.active_object.mode == 'OBJECT':
            if not strict:
                return False
            print(f'WARNING: Reverting {context.active_object.mode} into OBJECT mode on object {context.active_object.name}`.')
            bpy.ops.object.mode_set(mode='OBJECT')
            return True

    @staticmethod
    def saveSelectedObjectState(context):
        if not Utils.bAssertObjectMode(context, strict=False):
            return
        Utils.addon_previously_selected = context.selected_objects

    @staticmethod
    def loadSelectedObjectState(context):
        if not Utils.bAssertObjectMode(context, strict=False):
            return
        if Utils.addon_previously_selected:
            for o in Utils.addon_previously_selected:
                o.select_set(state=True)
            context.view_layer.objects.active = Utils.addon_previously_selected[0]
            Utils.addon_previously_selected = None


class ObjectUtils:
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
        """ Deletes objects data from scene """
        if objs:
            for obj in objs:
                bpy.data.objects.remove(obj, do_unlink=True) 
    
    @staticmethod
    def deleteObjectsWithPrefix(prefix: str):
        ObjectUtils.deleteObjectsFromScene(ObjectUtils.qAllBObjectsWithPrefix(prefix))

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
        """ Calculates relative bounding box dimension """
        rot = obj.rotation_euler.copy()
        dim = obj.dimensions.to_3d()
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        x, y, z = [ [ c[i] for c in corners ] for i in range(3) ]
        fcenter = lambda x: ( max(x) + min(x) ) / 2
        center = [ fcenter(axis) for axis in [x,y,z] ]
        return Vector(center), dim, rot

    @staticmethod
    def uMoveObjectAlongAxis(obj: BObject, axis=(0,0,1), offset: float = 0.0,):
        if not isinstance(axis, Vector):
            axis = Vector(axis)
        if isclose(offset, 0):
            return obj
        vec_offset = axis * offset
        mat_inv = obj.matrix_world.copy()
        mat_inv.invert()
        obj.location += vec_offset @ mat_inv
        return obj

    def uPivotObjectAlongTargetLocalAxis(obj: BObject, pivot_obj: BObject, pivot_axis_enum, offset_angle: float):
        if pivot_axis_enum not in ['X', 'Y', 'Z']:
            return obj
        if isclose(offset_angle, 0):
            return obj
        Utils.bAssertObjectMode(bpy.context, strict=True)
        Utils.saveSelectedObjectState(bpy.context)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(state=True)
        pivot_obj.select_set(state=True)
        bpy.context.view_layer.objects.active = pivot_obj
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
        pivot_obj.rotation_euler.rotate_axis(pivot_axis_enum, offset_angle)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.ops.object.select_all(action='DESELECT')
        pivot_obj.rotation_euler.rotate_axis(pivot_axis_enum, -offset_angle)
        Utils.loadSelectedObjectState(bpy.context)
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
        update=lambda a, b: ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('camera'))
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

    int_camera_rotation_increment: IntProperty(
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

class SPRSHTT_OP_CreateHelperObject(Operator):
    bl_idname = "object.sprshtt_create_helper_object"
    bl_label = "Create Helper Object on Target Object"

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties

        target_object = addon_prop.collection_target_objects
        if not target_object:
            return {'CANCELLED'}

        Utils.bAssertObjectMode(context)

        coord, dim, rot = ObjectUtils.uCalcObjectBboxDimension(target_object)

        ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix())

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

class SPRSHTT_OP_CreateCamera(Operator):
    """ Create custom camera """
    bl_idname = 'object.sprshtt_create_camera'
    bl_label = "Create Custom Camera"

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties
        objects = scene.objects
        target_object = addon_prop.collection_target_objects

        if not target_object:
            return {'CANCELLED'}

        is_helper_already_exist = False
        if ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')) and \
            ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-circle')):
            is_helper_already_exist = True
        else:
            bpy.ops.object.sprshtt_create_helper_object('EXEC_DEFAULT') # recreate helper objects

        if addon_prop.bool_existing_camera:
            context.scene.camera = ObjectUtils.qAllBObjectsWithPrefix('Camera')[0]
            return {'FINISHED'}

        ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('camera'))
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
        ObjectUtils.uMoveObjectAlongAxis(obj, (0,-1,0), camera_offset)
        obj.rotation_euler.rotate_axis('X', pi/2)
        context.scene.camera = obj
        addon_prop.collection_target_cameras = obj

        if not is_helper_already_exist:
            for t in ['axis-helper-arrow', 'axis-helper-circle']:
                ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix(t))

        return {'FINISHED'}

class SPRSHTT_OP_DeleteAllAddonObjects(Operator):
    bl_idname = 'object.sprshtt_delete_addon_objects'
    bl_label = "Delete All SPRSHTT Addon Object"
    def execute(self, context):
        ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix())
        return {'FINISHED'}

class SPRSHTT_OP_RotateCameraCW(Operator):
    bl_idname = 'object.sprshtt_rotate_camera_cw'
    bl_label = "Rotate Camera Clockwise"

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties
        camera_object = addon_prop.collection_target_cameras

        if not ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')):
            return {'CANCELLED'}
        helper_object = ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow'))[0]

        if not camera_object:
            return {'CANCELLED'}

        is_helper_already_exist = False
        if ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')) and \
            ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-circle')):
            is_helper_already_exist = True
        else:
            bpy.ops.object.sprshtt_create_helper_object('EXEC_DEFAULT')

        angle_offset = 2*pi/addon_prop.int_camera_rotation_increment

        if isclose(angle_offset, 2*pi):
            return {'CANCELLED'}

        ObjectUtils.uPivotObjectAlongTargetLocalAxis(camera_object, helper_object, 'Z', angle_offset)

        if not is_helper_already_exist:
            for t in ['axis-helper-arrow', 'axis-helper-circle']:
                ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix(t))

        return {'FINISHED'}

class SPRSHTT_OP_RotateCameraCCW(Operator):
    bl_idname = 'object.sprshtt_rotate_camera_ccw'
    bl_label = "Rotate Camera Counter-Clockwise"
    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties
        camera_object = addon_prop.collection_target_cameras

        if not ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')):
            return {'CANCELLED'}
        helper_object = ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow'))[0]

        if not camera_object:
            return {'CANCELLED'}

        is_helper_already_exist = False
        if ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')) and \
            ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-circle')):
            is_helper_already_exist = True
        else:
            bpy.ops.object.sprshtt_create_helper_object('EXEC_DEFAULT') # recreate helper objects

        angle_offset = -2*pi/addon_prop.int_camera_rotation_increment

        if isclose(angle_offset, -2*pi):
            return {'CANCELLED'}

        ObjectUtils.uPivotObjectAlongTargetLocalAxis(camera_object, helper_object, 'Z', angle_offset)

        if not is_helper_already_exist:
            # delete helper objects from recreation
            for t in ['axis-helper-arrow', 'axis-helper-circle']:
                ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix(t))

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
        col.operator('object.sprshtt_delete_addon_objects', text='Delete Addon Objects')
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
        subsubcol = subcol.column()
        subsubcol.enabled = not addon_prop.bool_auto_camera_offset
        subsubcol.prop(addon_prop, 'float_distance_offset')
        subcol.prop(addon_prop, 'fvec_camera_target_pos_offset')
        subcol.prop(addon_prop, 'fvec_camera_target_rot_offset')
        subcol.operator('object.sprshtt_create_camera', text='Spawn Camera')
        ## ColGroup 3
        subcol = col.column()
        row = subcol.row()
        row.enabled = bool(addon_prop.collection_target_cameras)
        row.operator('object.sprshtt_rotate_camera_cw', text='CW')
        row.operator('object.sprshtt_rotate_camera_ccw', text='CCW')

class SPRSHTT_PT_render_panel_renderer(SPRSHTT_Panel_baseProps, bpy.types.Panel):
    bl_label = "Renderer Settings"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene
        col = layout.column()
        col.prop(addon_prop, 'int_camera_rotation_increment')
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
    SPRSHTT_OP_CreateHelperObject,
    SPRSHTT_OP_CreateCamera,
    SPRSHTT_OP_DeleteAllAddonObjects,
    SPRSHTT_OP_RotateCameraCW,
    SPRSHTT_OP_RotateCameraCCW,
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

    
    