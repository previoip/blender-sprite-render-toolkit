# Blender Addon: Sprite Sheet Render Toolkit

# About

Blender addon for consistent rendering 3D Objects into bitmap assets. 

- Tested on Blender 2.80
- Renders object and animations, additionally with frame-skipping 
- ***Does not support rendering collections and animation groups***
- Still needs to adjust manually for frame-range (a little bit of warning before you render worth of 250 frames unknowingly)

# Installing

This was written into a monolithic python file (as it was created only as a script) thus installing this addon can be as straight forward as importing the main file into Blender `Scripting` tab then run the script, which will append the addon properties into your project. This method however is not recommended since doing this way will yield in confusion on uninstalling the addon itself (me included).

The other way is to [install the addon](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html) with the file `sprite-sheet-render-toolkit.py` as addon file target.

# Addendum

