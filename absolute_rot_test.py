bl_info = {
    "name": "Euler Rot Test",
    "blender": (2, 80, 0),
    "category": "Render",
    "version": (0, 0, 1),
    "location": "View3D > Properties > Render",
}

import bpy
import os
from random import getrandbits
from bpy.types import (
    PropertyGroup,
    Operator,
)
from bpy.props import (
    IntProperty,
    PointerProperty
)
from mathutils import Vector, Matrix, Euler
from math import pi, sqrt, log2, isclose


def incrementUpdateCallback(s, c):
    print('increment updated')
    print('value :', s.int_increment)
    print('target obj :', s.collection_target_objects)

    s.collection_target_objects.rotation_euler[0] = (s.int_increment/8) * 2 * pi

class FooProps(PropertyGroup):

    int_increment: IntProperty(
        name='increment',
        max=8,
        min=0,
        default=2,
        update=incrementUpdateCallback,
    )

    collection_target_objects: PointerProperty(
        type=bpy.types.Object, 
        poll=lambda s, x: x.type == 'MESH',
        name='Target'
    )

class FOO_PT_Panel(bpy.types.Panel):
    bl_space_type   = 'PROPERTIES'
    bl_region_type  = 'WINDOW'
    bl_context      = 'render'
    bl_label        = '<<test>>'

    def draw(self, context):
        layout = self.layout
        prop = context.scene.foo_props
        col = layout.column()
        col.prop(prop, 'int_increment')
        col.prop(prop, 'collection_target_objects')
        col.operator('object.count_up_increment', text='C')


class FOO_OP_Increment(Operator):
    bl_idname = 'object.count_up_increment'
    bl_label = "Iterate increment"

    def execute(self, context):
        scene = context.scene
        prop = context.scene.foo_props

        prop.int_increment += 1

        if prop.int_increment >= 8:
            prop.int_increment = 0
        print(prop.int_increment)
        return {'FINISHED'}

classes = (FooProps, FOO_PT_Panel, FOO_OP_Increment)

def register():
    print('registering module')
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.foo_props = PointerProperty(type=FooProps)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    delattr(bpy.types.Scene, 'foo_props')

if __name__ == '__main__':
    register()