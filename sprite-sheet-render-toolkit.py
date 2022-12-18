bl_info = {
    "name": "Sprite Sheet Render Toolkit",
    "blender": (2, 80, 0),
    "category": "Render",
    "support": "COMMUNITY",
    "author": "Previo Prakasa (github.com/previoip)",
    "version": (0, 0, 2),
    "location": "View3D > Properties > Render",
    "description": "Render toolkit using camera manipulation for generating 2D sprite sheet from 3D assets.",
    "warning": "This is an experimental project and should not be used in any form of production (as of today).",
}

import bpy
import os
from random import getrandbits
from bpy.types import (
    Scene,
    PropertyGroup,
    Operator,
    Panel,
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
from bpy.path import (
    abspath,
    relpath,
    clean_name,
    native_pathsep
)
from mathutils import (
    Vector,
    Matrix,
    Euler
)
from math import (
    pi,
    log2,
    isclose,
    radians
)


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

    @staticmethod
    def iWrapAround(n, min_v, max_v):
        n_range = max_v - min_v
        n = n % n_range
        return min_v + n


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
    def uDecomposeObjectBboxDimension(obj: BObject):
        """ Calculates relative bounding box dimension """
        rot = obj.rotation_euler.copy()
        dim = obj.dimensions.to_3d()
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        x, y, z = [ [ c[i] for c in corners ] for i in range(3) ]
        fcenter = lambda x: ( max(x) + min(x) ) / 2
        center = [ fcenter(axis) for axis in [x,y,z] ]
        return Vector(center), dim, rot

    @staticmethod
    def uMoveObjectAlongVector(obj: BObject, vec=(0,0,1), offset: float = 0.0):
        if not isinstance(vec, Vector):
            vec = Vector(vec)
        if isclose(offset, 0):
            return obj
        vec_offset = vec * offset

        # personal side note: 
        # using matrix world for relative transformation yields some side
        # effect where past rotation transformation is preserved throughout.
        # This causes the cross-product below to deviates in the wrong 
        # direction, a frustrating bug to find.
        # One solution is to recalc world matrix using C.view_layer.update
        # but for various reason this is also to be avoided since its 
        # relatively heavy operation. 

        # Thus in this implementation a simple bounce back transformation
        # to world origin and apply the translation that way.

        # bpy.context.view_layer.update()
        # mat_inv = obj.matrix_world.copy()
        # mat_inv.invert()
        # obj.location += vec_offset @ mat_inv

        last_pos = obj.location.copy()
        obj.location -= last_pos
        obj.location += vec_offset
        obj.location += last_pos
        return obj

    @staticmethod
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


class EventHandlers:

    @staticmethod
    def camRotationCounterCallback(_self, context):
        if _self.int_camera_rotation_increment_limit <= _self.int_camera_rotation_preview:
            _self.int_camera_rotation_preview = _self.int_camera_rotation_increment_limit - 1
        EventHandlers.camIncrUpdateCallback(_self, context)

    @staticmethod
    def camUpdateCallback(_self, context):
        camera_object = _self.collection_target_cameras
        target_object = _self.collection_target_objects
        _, target_dim, _  = ObjectUtils.uDecomposeObjectBboxDimension(target_object)

        if not camera_object or not target_object:
            return
        if not Utils.bAssertObjectMode(context, strict=False):
            return
        if not ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow')):
            return
        helper_object = ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow'))[0]

        loc, _, rot = ObjectUtils.uDecomposeObjectBboxDimension(helper_object)
        Subroutine.setCameraTransformation(
            camera_object, 
            loc, 
            rot, 
            Vector((_self.float_distance_offset,0,0)), 
            Euler((_self.float_camera_angle_pitch, _self.float_camera_angle_roll, _self.float_camera_angle_yaw))
        )

        Subroutine.setCameraIntrinsic(
            camera_object, 
            _self.enum_camera_type, 
            (
                _self.float_distance_offset - target_dim.length * 1.5,
                _self.float_distance_offset + target_dim.length * 1.5,
            ),
            _self.float_camera_field_of_view,
            _self.float_camera_ortho_scale
        )

        angle = (_self.int_camera_rotation_preview/_self.int_camera_rotation_increment_limit) * 2 * pi
        ObjectUtils.uPivotObjectAlongTargetLocalAxis(camera_object, helper_object, 'Z', angle)

    @staticmethod
    def camIncrUpdateCallback(_self, context):
        # side note:
        # updating the value directly from context->scene->prop will call the setter event on the attr instead,
        # thus this will not trigger update event on _self and cause infinite recursion!
        scene = context.scene
        addon_prop = scene.sprshtt_properties

        addon_prop['int_camera_rotation_preview'] = \
            Utils.iWrapAround(_self.int_camera_rotation_preview, 0, _self.int_camera_rotation_increment_limit)
        EventHandlers.camUpdateCallback(_self, context)

    @staticmethod
    def frameSkipUpdateCallback(_self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties

        frame_start = scene.frame_start
        frame_end = scene.frame_end
        frame_range = frame_end - frame_start
        frame_skip = addon_prop.int_frame_skip
        addon_prop['int_frame_skip'] = min(frame_range, frame_skip)


class Subroutine:
    
    @staticmethod
    def setCameraTransformation(camera_object: BObject, location: Vector, rotation: Euler, location_offset: Vector, yaw_pitch_roll: Euler):
        camera_object.location = location
        roll = yaw_pitch_roll.y
        yaw_pitch_roll = Euler((pi/2 - yaw_pitch_roll.x, 0, pi/2 + yaw_pitch_roll.z))
        rotation = (rotation.to_matrix() @ yaw_pitch_roll.to_matrix()).to_euler(camera_object.rotation_mode)
        camera_object.rotation_euler = rotation
        up_vec = Vector((0,0,1))
        up_vec.rotate(rotation)
        ObjectUtils.uMoveObjectAlongVector(
            camera_object, 
            up_vec,
            location_offset.length
        )
        camera_object.rotation_euler.rotate_axis('Z', roll)

    def setCameraIntrinsic(camera_object: BObject, camera_type: str, camera_clipping_limit: tuple, camera_fov: float, camera_ortho_scale: float):
        camera_object.data.type = camera_type
        camera_object.data.clip_start = max(10e-8, camera_clipping_limit[0])
        camera_object.data.clip_end = max(10e-8, camera_clipping_limit[1])
        if camera_type == 'ORTHO':
            camera_object.data.ortho_scale = camera_ortho_scale
        elif camera_type == 'PERSP':
            camera_object.data.angle = camera_fov


# Addon Properties

class SPRSHTT_PropertyGroup(PropertyGroup):

    str_export_folder: StringProperty(
        name='Export Folder', 
        description = 'Export subfolder',
        default='export'
        )

    str_file_suffix: StringProperty(
        name='Suffix', 
        description = 'Export images suffix',
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

    bool_copy_target_local_transformation: BoolProperty(
        name='Copy Target Transformation',
        description = 'Spawn camera and copy target local transformation, if unselected then helper will follow global rotation.',
        default=False,
        )

    float_camera_ortho_scale: FloatProperty(
        name='Ortho Scale', 
        description = 'Orthographic Scale',
        default=3.4,
        min=.0, 
        precision=3,
        subtype='UNSIGNED',
        update=EventHandlers.camUpdateCallback
        )

    # float_camera_focal_length: FloatProperty(
    #     name='Focal Length', 
    #     description = 'Perspective Focal Length',
    #     default=75.0,
    #     min=1, 
    #     precision=1,
    #     subtype='UNSIGNED',
    #     unit='CAMERA',
    #     update=EventHandlers.camUpdateCallback
    #     )

    float_camera_field_of_view: FloatProperty(
        name='Field of View', 
        description = 'Perspective Field of View',
        default=radians(39.6),
        min=radians(.367),
        max=radians(173),
        precision=3,
        subtype='UNSIGNED',
        unit='ROTATION',
        update=EventHandlers.camUpdateCallback
        )


    enum_camera_type: EnumProperty(
        name='Type', 
        description = 'Change default camera type',
        items = [
            ("ORTHO", "Orthographic", "", 1),
            ("PERSP", "Perspective", "", 2),
        ],
        default="ORTHO",
        update=EventHandlers.camUpdateCallback
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
        soft_max=1000,
        update=EventHandlers.frameSkipUpdateCallback
        )

    # Todo:
    # fvec_camera_yaw_pitch_roll: FloatVectorProperty(
    #     name='Yaw Pitch Roll', 
    #     default=(0.0, radians(57.3), 0.0), 
    #     unit='ROTATION'
    #     )

    float_camera_angle_pitch: FloatProperty(
        name='Pitch', 
        description = 'Camera Pitch',
        default=radians(57.3),
        min=-pi, 
        max=pi, 
        precision=2,
        subtype='ANGLE',
        update=EventHandlers.camUpdateCallback
        )

    float_camera_angle_yaw: FloatProperty(
        name='Yaw', 
        description = 'Camera Yaw',
        default=0, 
        min=-pi,
        max=pi,
        precision=2,
        subtype='ANGLE',
        update=EventHandlers.camUpdateCallback
        )

    float_camera_angle_roll: FloatProperty(
        name='Roll',
        description = 'Camera Roll',
        default=0, 
        min=-pi,
        max=pi,
        precision=2,
        subtype='ANGLE',
        update=EventHandlers.camUpdateCallback
        )


    int_camera_rotation_increment_limit: IntProperty(
        name='Increment', 
        description = 'Camera n of increment in one render cycle (rotates 360 degrees).',
        default=8, 
        min=1, 
        soft_max=36,
        max=99,
        update=EventHandlers.camRotationCounterCallback
        )

    int_camera_rotation_preview: IntProperty(
        default=0, 
        min=0, 
        soft_max=36,
        max=99,
        update=EventHandlers.camIncrUpdateCallback
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
        update=EventHandlers.camUpdateCallback
        )

    bool_auto_camera_scale: BoolProperty(
        name='Auto Camera Scale', 
        description = 'Automatically set camera scale by object bounding-box size',
        default=False,
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
    
    # additional 'private' property as extra value container
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

        coord, dim, rot = ObjectUtils.uDecomposeObjectBboxDimension(target_object)

        if not addon_prop.bool_copy_target_local_transformation:
            rot = Euler((0,0,0))

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
        target_object = addon_prop.collection_target_objects

        if not target_object:
            return {'CANCELLED'}

        Utils.bAssertObjectMode(context)

        if ObjectUtils.bBObjectsHasPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper')):
            bpy.ops.object.sprshtt_create_helper_object('EXEC_DEFAULT') # recreate helper objects

        if addon_prop.bool_existing_camera:
            context.scene.camera = ObjectUtils.qAllBObjectsWithPrefix('Camera')[0]
            return {'FINISHED'}

        ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('camera'))
        helper_object = ObjectUtils.qAllBObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix('axis-helper-arrow'))[0]

        camera_offset = addon_prop.float_distance_offset
        _, target_dim, _  = ObjectUtils.uDecomposeObjectBboxDimension(target_object)
        loc, dim, rot = ObjectUtils.uDecomposeObjectBboxDimension(helper_object)
        if addon_prop.bool_auto_camera_offset:
            camera_offset = helper_object.empty_display_size + log2(target_dim.length + 1) * 8
        addon_prop.float_distance_offset = camera_offset

        bpy.ops.object.camera_add()
        obj = context.selected_objects[0]
        obj.data.show_sensor = True
        obj.data.show_limits = True
        obj.name = ObjectUtils.sGenerateUniqueObjectName('camera')
        context.scene.camera = obj
        addon_prop.collection_target_cameras = obj
        EventHandlers.camUpdateCallback(addon_prop, context)

        addon_prop.int_camera_rotation_preview = 0

        return {'FINISHED'}


class SPRSHTT_OP_DeleteAllAddonObjects(Operator):
    bl_idname = 'object.sprshtt_delete_addon_objects'
    bl_label = "Delete All SPRSHTT Addon Object"
    def execute(self, context):
        ObjectUtils.deleteObjectsWithPrefix(ObjectUtils.sGetDefaultPrefix())
        return {'FINISHED'}


class SPRSHTT_OP_Render(Operator):
    bl_idname = "object.sprshtt_render"
    bl_label = "Do you really want to do that?"
    bl_options = {'REGISTER', 'INTERNAL'} # internal option removes operator from blender search

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        scene = context.scene
        addon_prop = scene.sprshtt_properties

        target_name = addon_prop.collection_target_objects.name
        render_subfolder = addon_prop.str_export_folder
        render_file_suffix = addon_prop.str_file_suffix
        render_file_format = scene.render.image_settings.file_format
        render_fp = abspath(scene.render.filepath)
        render_fp = native_pathsep(render_fp)

        bitmap_file_formats = ['PNG', 'BMP', 'JPEG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'IRIS']
        if render_file_format not in bitmap_file_formats:
            self.report({'INFO'}, f'File format not supported: {render_file_format}')
            return {'CANCELLED'}

        if not render_file_suffix:
            render_file_suffix = target_name
        render_file_suffix = clean_name(render_file_suffix)

        if render_subfolder:
            render_subfolder = native_pathsep(render_subfolder).lstrip(os.path.sep)
            render_fp = os.path.join(render_fp, render_subfolder)
            if not os.path.isdir(render_fp):
                os.mkdir(render_fp)
                self.report({'INFO'}, f'Created new folder {render_fp}')

        frame_start = scene.frame_start
        frame_end = scene.frame_end
        frame_range = frame_end - frame_start
        frame_skip = addon_prop.int_frame_skip
        if not addon_prop.bool_frame_skip:
            frame_skip = 1

        render_sub_sub_folder = os.path.join(render_fp, render_file_suffix)
        if not os.path.isdir(render_sub_sub_folder):
            os.mkdir(render_sub_sub_folder)
            self.report({'INFO'}, f'Created new folder {render_sub_sub_folder}')
        
        for inc in range(addon_prop.int_camera_rotation_increment_limit):
            addon_prop.int_camera_rotation_preview = inc
            curr_angle = inc*360//addon_prop.int_camera_rotation_increment_limit

            render_sub_sub_sub_folder = os.path.join(render_sub_sub_folder, f'd{curr_angle:03}_{render_file_suffix}')

            if not os.path.isdir(render_sub_sub_sub_folder):
                os.mkdir(render_sub_sub_sub_folder)
                self.report({'INFO'}, f'Created new folder {render_sub_sub_sub_folder}')

            frame = frame_start
            while frame < frame_end:
                scene.frame_current = frame
                frame += frame_skip
                filename = f'f{frame:06}.{render_file_format.lower()}'
                Utils.renderToPath(context, render_sub_sub_sub_folder, filename)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_confirm(self, event)
        return {'FINISHED'}


# Addon UIs

class SPRSHTT_Panel_baseProps:
    bl_space_type   = 'PROPERTIES'
    bl_region_type  = 'WINDOW'
    bl_context      = 'render'

class SPRSHTT_PT_render_panel(SPRSHTT_Panel_baseProps, Panel):
    bl_label        = '< Sprite Sheet Toolkit >'
    bl_options      = {'DEFAULT_CLOSED'}

    def draw(self, context):
        pass

class SPRSHTT_PT_render_panel_addon(SPRSHTT_Panel_baseProps, Panel):
    bl_label = "Addon Settings"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene

        col = layout.column()
        col.operator('object.sprshtt_delete_addon_objects', text='Delete Addon Objects')
        col.prop(addon_prop, 'collection_target_objects' )

        subcol = col.column()
        subcol.enabled = bool(addon_prop.collection_target_objects)
        subcol.prop(addon_prop, 'bool_copy_target_local_transformation')
        subcol.operator('object.sprshtt_create_helper_object', text='Spawn Target Helper')

        subcol = col.column()
        subcol.enabled = False # addon_prop.bool_existing_camera 
        subcol.prop(addon_prop, 'collection_target_cameras')

        subcol = col.column()
        subcol.enabled = not addon_prop.bool_existing_camera
        subcol.prop(addon_prop, 'enum_camera_type')

        if addon_prop.enum_camera_type == 'PERSP':
            subcol.prop(addon_prop, 'float_camera_field_of_view')
        elif addon_prop.enum_camera_type == 'ORTHO':
            subcol.prop(addon_prop, 'float_camera_ortho_scale')

        subrow = subcol.row(align=True)
        subcol.enabled = bool(addon_prop.collection_target_objects)
        subrow.prop(addon_prop, 'float_camera_angle_pitch')
        subrow.prop(addon_prop, 'float_camera_angle_yaw')
        subrow.prop(addon_prop, 'float_camera_angle_roll')
        subcol.prop(addon_prop, 'bool_auto_camera_offset')
        subsubcol = subcol.column()
        subsubcol.enabled = not addon_prop.bool_auto_camera_offset
        subsubcol.prop(addon_prop, 'float_distance_offset')
        subcol.operator('object.sprshtt_create_camera', text='Spawn Camera')


class SPRSHTT_PT_render_panel_renderer(SPRSHTT_Panel_baseProps, Panel):
    bl_label = "Renderer Settings"
    bl_parent_id = "SPRSHTT_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        addon_prop = context.scene.sprshtt_properties
        scene = context.scene

        col = layout.column()
        col.prop(addon_prop, 'int_camera_rotation_increment_limit')
        subcol = col.column()
        subcol.enabled = bool(addon_prop.collection_target_cameras)
        subcol.prop(addon_prop, 'int_camera_rotation_preview', text='Preview')

        col.prop(addon_prop, 'bool_frame_skip')
        subcol = col.column()
        if addon_prop.bool_frame_skip:
            subcol.prop(addon_prop, 'int_frame_skip')

class SPRSHTT_PT_render_panel_output(SPRSHTT_Panel_baseProps, Panel):
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

        subcol = col.column()
        subcol.enabled = bool(addon_prop.collection_target_cameras)
        subcol.operator('object.sprshtt_render', text='Render')


# Addon Register/Unregister

classes = (
    SPRSHTT_PT_render_panel,
    SPRSHTT_PT_render_panel_addon,
    SPRSHTT_PT_render_panel_renderer,
    SPRSHTT_PT_render_panel_output, 
    SPRSHTT_OP_CreateHelperObject,
    SPRSHTT_OP_CreateCamera,
    SPRSHTT_OP_Render,
    SPRSHTT_OP_DeleteAllAddonObjects,
    SPRSHTT_PropertyGroup,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    Scene.sprshtt_properties = PointerProperty(type=SPRSHTT_PropertyGroup)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    delattr(Scene, 'sprshtt_properties')

if __name__ == '__main__':
    register()