"""
Utility functions for manipulating objects in Blender

Xiuming Zhang, MIT CSAIL
July 2017
"""

import logging
import re
from os.path import abspath
import numpy as np
import bpy
from mathutils import Matrix

logging.basicConfig(level=logging.INFO)
thisfile = abspath(__file__)


def remove_object(name_pattern):
    """
    Remove object from current scene

    Args:
        name_pattern: Names of objects to remove
            String (regex supported)
            Use '.*' to remove all objects
    """
    thisfunc = thisfile + '->clear_all()'

    # Regex
    assert (name_pattern != '*'), "Want to match everything? Correct regex for this is '.*'"
    name_pattern = re.compile(name_pattern)

    objs = bpy.data.objects
    removed = []
    for obj in objs:
        if name_pattern.match(obj.name):
            obj.select = True
            removed.append(obj.name)
        else:
            obj.select = False
    bpy.ops.object.delete()

    logging.info("%s: Removed from scene: %s", thisfunc, removed)


def add_object(model_path, rot_mat=((1, 0, 0), (0, 1, 0), (0, 0, 1)), trans_vec=(0, 0, 0), name=None):
    """
    Add object to current scene, the low-level way

    Args:
        model_path: Path to object to add
            String
        rot_mat: 3D rotation matrix PRECEDING translation
            Tuple, list or numpy array; must be effectively 3-by-3
            Optional; defaults to identity matrix
        trans_vec: 3D translation vector FOLLOWING rotation
            Tuple, list or numpy array; must be of length 3
            Optional; defaults to zero vector
        name: Object name after import
            String
            Optional; defaults to name specified in model

    Returns:
        obj: Handle of imported object
            bpy_types.Object
    """
    thisfunc = thisfile + '->add_object()'

    # Import
    if model_path.endswith('.obj'):
        bpy.ops.import_scene.obj(filepath=model_path, axis_forward='-Z', axis_up='Y')
    else:
        raise NotImplementedError("Importing model of this type")
    obj = bpy.context.selected_objects[0]

    # Rename
    if name is not None:
        obj.name = name

    # Compute world matrix
    trans_4x4 = Matrix.Translation(trans_vec)
    rot_4x4 = Matrix(rot_mat).to_4x4()
    scale_4x4 = Matrix(np.eye(4)) # no scaling
    obj.matrix_world = trans_4x4 * rot_4x4 * scale_4x4

    logging.info("%s: Imported: %s", thisfunc, model_path)

    return obj