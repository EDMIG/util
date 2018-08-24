"""
Utility functions for Blender renderings

Xiuming Zhang, MIT CSAIL
July 2017
"""

from os import makedirs
from os.path import abspath, dirname, exists, join
from shutil import move
from time import time
import bpy

import config
logger, thisfile = config.create_logger(abspath(__file__))


def set_cycles(w=None, h=None,
               n_samples=None, max_bounces=None, min_bounces=None,
               transp_bg=None,
               color_mode=None, color_depth=None):
    """
    Set up Cycles as rendering engine

    Args:
        w, h: Width, height of render in pixels
            Positive integer
            Optional; no change if not given
        n_samples: Number of samples
            Positive integer
            Optional; no change if not given
        max_bounces, min_bounces: Maximum, minimum number of light bounces
            Setting max_bounces to 0 for direct lighting only
            Natural number
            Optional; no change if not given
        transp_bg: Whether world background is transparent
            Boolean
            Optional; no change if not given
        color_mode: Color mode
            'BW', 'RGB' or 'RGBA'
            Optional; no change if not given
        color_depth: Color depth
            '8' or '16'
            Optional; no change if not given
    """
    logger_name = thisfile + '->set_cycles()'

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    cycles = scene.cycles

    cycles.use_progressive_refine = True
    if n_samples is not None:
        cycles.samples = n_samples
    if max_bounces is not None:
        cycles.max_bounces = max_bounces
    if min_bounces is not None:
        cycles.min_bounces = min_bounces
    cycles.caustics_reflective = False
    cycles.caustics_refractive = False
    cycles.diffuse_bounces = 10
    cycles.glossy_bounces = 4
    cycles.transmission_bounces = 4
    cycles.volume_bounces = 0
    cycles.transparent_min_bounces = 8
    cycles.transparent_max_bounces = 64

    # Avoid grainy renderings (fireflies)
    world = bpy.data.worlds['World']
    world.cycles.sample_as_light = True
    cycles.blur_glossy = 5
    cycles.sample_clamp_indirect = 5

    # Ensure there's no background light emission
    world.use_nodes = True
    try:
        world.node_tree.nodes.remove(world.node_tree.nodes['Background'])
    except KeyError:
        pass

    # If world background is transparent with premultiplied alpha
    if transp_bg is not None:
        cycles.film_transparent = transp_bg

    # # Use GPU
    # bpy.context.user_preferences.system.compute_device_type = 'CUDA'
    # bpy.context.user_preferences.system.compute_device = 'CUDA_' + str(randint(0, 3))
    # scene.cycles.device = 'GPU'

    scene.render.tile_x = 16 # 256 optimal for GPU
    scene.render.tile_y = 16 # 256 optimal for GPU
    if w is not None:
        scene.render.resolution_x = w
    if h is not None:
        scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.render.image_settings.file_format = 'PNG'
    if color_mode is not None:
        scene.render.image_settings.color_mode = color_mode
    if color_depth is not None:
        scene.render.image_settings.color_depth = color_depth

    logger.name = logger_name
    logger.info("Cycles set up as rendering engine")


def easyset(w=None, h=None,
            n_samples=None,
            ao=None,
            color_mode=None,
            file_format=None,
            color_depth=None):
    """
    Set some of the scene attributes more easily

    Args:
        w, h: Width, height of render in pixels
            Integer
            Optional; no change if not given
        n_samples: Number of samples
            Integer
            Optional; no change if not given
        ao: Ambient occlusion
            Boolean
            Optional; no change if not given
        color_mode: Color mode of rendering
            'BW', 'RGB', or 'RGBA'
            Optional; no change if not given
        file_format: File format of the render
            'PNG', 'OPEN_EXR', etc.
            Optional; no change if not given
        color_depth: Color depth of rendering
            '8' or '16' for .png; '16' or '32' for .exr
            Optional; no change if not given
    """
    scene = bpy.context.scene
    engine = scene.render.engine

    if w is not None:
        scene.render.resolution_x = w

    if h is not None:
        scene.render.resolution_y = h

    # Number of samples
    if n_samples is not None:
        if engine == 'CYCLES':
            scene.cycles.samples = n_samples
        else:
            raise NotImplementedError(engine)

    # Ambient occlusion
    if ao is not None:
        bpy.context.scene.world.light_settings.use_ambient_occlusion = ao

    # Color mode of rendering
    if color_mode is not None:
        scene.render.image_settings.color_mode = color_mode

    # File format of the render
    if file_format is not None:
        scene.render.image_settings.file_format = file_format

    # Color depth of rendering
    if color_depth is not None:
        scene.render.image_settings.color_depth = color_depth


def render(outpath, text=None, cam_names=None, hide=None):
    """
    Render current scene to images with cameras in scene

    Args:
        outpath: Path to save render to, e.g., '~/foo.png'
            String
        text: What text to be overlaid on image and how
            Dictionary of the following format
            {
                'contents': 'Hello World!',
                'bottom_left_corner': (50, 50),
                'font_scale': 1,
                'bgr': (255, 0, 0),
                'thickness': 2
            }
            Optional; defaults to None
        cam_names: Name(s) of camera(s) through which scene is rendered
            String or list thereof
            Optional; defaults to None (render all cameras)
        hide: What objects should be hidden from which camera
            Dictionary of the following format
            {
                'name-of-cam1': 'name-of-obj1',
                'name-of-cam2': ['name-of-obj1', 'name-of-obj2']
                    ...
            }
            Optional; defaults to None

    Returns:
        result_path: Path(s) to the rendering ('outpath' suffixed by camera name)
            String or list thereof
    """
    import cv2

    logger_name = thisfile + '->render()'

    if isinstance(cam_names, str):
        cam_names = [cam_names]

    outdir = dirname(outpath)
    if not exists(outdir):
        makedirs(outdir)

    result_path = []

    # Save original hide_render attributes for later restoration
    renderability = {}
    objects = bpy.data.objects
    for obj in objects:
        renderability[obj.name] = obj.hide_render

    # Render with all cameras
    for cam in objects:
        if cam.type == 'CAMERA':
            if cam_names is None or cam.name in cam_names:

                # Set active camera
                bpy.context.scene.camera = cam

                # Append camera name
                ext = outpath.split('.')[-1]
                outpath_final = outpath.replace('.' + ext, '_%s.' % cam.name + ext)
                bpy.context.scene.render.filepath = outpath_final
                result_path.append(outpath_final)

                # Optionally set object visibility in rendering
                for obj in objects:
                    if obj.type == 'MESH':
                        if hide is not None:
                            ignore_list = hide.get(cam.name, [])
                            if not isinstance(ignore_list, list):
                                # Single object
                                ignore_list = [ignore_list]
                            obj.hide_render = obj.name in ignore_list
                        else:
                            obj.hide_render = False

                # Render
                bpy.ops.render.render(write_still=True)

                # Optionally overlay text
                if text is not None:
                    im = cv2.imread(outpath_final, cv2.IMREAD_UNCHANGED)
                    cv2.putText(im, text['contents'], text['bottom_left_corner'],
                                cv2.FONT_HERSHEY_SIMPLEX, text['font_scale'],
                                text['bgr'], text['thickness'])
                    cv2.imwrite(outpath_final, im)

                logger.name = logger_name
                logger.info("Rendered with camera '%s'", cam.name)

    # Restore hide_render attributes
    for obj_name, hide_render_value in renderability.items():
        objects[obj_name].hide_render = hide_render_value

    if len(result_path) == 1:
        return result_path[0]
    return result_path


def render_depth(outpath, cam=None, obj_names=None, ray_depth=False):
    """
    Render depth map of the specified object(s) from the specified camera

    Args:
        outpath: Where to save the .exr depth map
            String
        cam: Camera through which scene is rendered
            bpy_types.Object or None
            Optional; defaults to None (the only camera in scene)
        obj_names: Name(s) of object(s) of interest
            String or list thereof
            Optional; defaults to None (all objects)
        ray_depth: Whether to render ray or plane depth
            Boolean
            Optional; defaults to False (plane depth)
    """
    logger_name = thisfile + '->render_depth()'

    if cam is None:
        cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
        assert (len(cams) == 1), ("There should be exactly one camera in the scene, "
                                  "when 'cam' is not given")
        cam = cams[0]

    if isinstance(obj_names, str):
        obj_names = [obj_names]
    elif obj_names is None:
        obj_names = [o.name for o in bpy.data.objects if o.type == 'MESH']

    scene = bpy.context.scene
    scene.cycles.samples = 1 # engine not necessarily being Cycles

    # Set active camera
    scene.camera = cam

    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            obj.hide_render = obj.name not in obj_names

    if ray_depth:
        raise NotImplementedError("Ray depth")

    # Set nodes for z pass rendering
    scene.use_nodes = True
    node_tree = scene.node_tree
    nodes = node_tree.nodes
    nodes.new('CompositorNodeOutputFile')
    nodes['File Output'].format.file_format = 'OPEN_EXR'
    nodes['File Output'].format.color_depth = '32'
    nodes['File Output'].format.color_mode = 'RGB'
    nodes['File Output'].base_path = '/tmp/%s' % time()
    scene.render.filepath = '/tmp/%s' % time()
    node_tree.links.new(nodes['Render Layers'].outputs['Z'],
                        nodes['File Output'].inputs['Image'])

    # Render
    bpy.ops.render.render(write_still=True)

    # Move from temporary directory
    if not outpath.endswith('.exr'):
        outpath += '.exr'
    move(join(nodes['File Output'].base_path, 'Image0001.exr'), outpath)

    logger.name = logger_name
    logger.info("Depth map of %s rendered through '%s' to %s", obj_names, cam.name, outpath)
    logger.warning("    ..., and the scene node tree has changed")


def render_mask(outpath, cam=None, obj_names=None):
    """
    Render binary masks of objects from the specified camera

    Args:
        outpath: Path to save render to, e.g., '~/foo.png'
            String
        cam: Camera through which scene is rendered
            bpy_types.Object or None
            Optional; defaults to None (the only camera in scene)
        obj_names: Name(s) of object(s) of interest
            String or list thereof
            Optional; defaults to None (all objects)
    """
    import numpy as np
    import cv2

    logger_name = thisfile + '->render_mask()'

    # Render depth
    depth_path = '/tmp/%s.exr' % time()
    render_depth(depth_path, cam=cam, obj_names=obj_names, ray_depth=False)

    # Binarize depth into mask
    depth = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)[..., 0]
    is_fg = depth < depth.max()
    mask = np.zeros(is_fg.shape)
    mask[is_fg] = 255

    outdir = dirname(outpath)
    if not exists(outdir):
        makedirs(outdir)

    cv2.imwrite(outpath, mask)

    logger.name = logger_name
    logger.info("Binary mask of %s rendered through '%s'", obj_names, cam.name)
    logger.warning("    ...; node trees and renderability of these objects have changed")


def render_normal(outpath, cam=None, obj_names=None, camera_space=True):
    """
    Render normal map of the specified object(s) from the specified camera
        RGB at each pixel is the (almost unit) normal vector

    Args:
        outpath: Where to save the .exr (i.e., raw) normal map
            String
        cam: Camera through which scene is rendered
            bpy_types.Object or None
            Optional; defaults to None (the only camera in scene)
        obj_names: Name(s) of object(s) of interest
            String or list thereof
            Optional; defaults to None (all objects)
        camera_space: Whether to render normal in the camera or world space
            Boolean
            Optional; defaults to True
    """
    logger_name = thisfile + '->render_normal()'

    if cam is None:
        cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
        assert (len(cams) == 1), ("There should be exactly one camera in the scene, "
                                  "when 'cam' is not given")
        cam = cams[0]

    if isinstance(obj_names, str):
        obj_names = [obj_names]
    elif obj_names is None:
        obj_names = [o.name for o in bpy.data.objects if o.type == 'MESH']

    scene = bpy.context.scene

    # Set active camera
    scene.camera = cam

    # Hide objects to ignore
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            obj.hide_render = obj.name not in obj_names

    # Set up scene node tree
    scene.use_nodes = True
    node_tree = scene.node_tree
    nodes = node_tree.nodes
    scene.render.layers['RenderLayer'].use_pass_normal = True
    nodes.new('CompositorNodeOutputFile')
    nodes['File Output'].format.file_format = 'OPEN_EXR'
    nodes['File Output'].format.color_depth = '32'
    nodes['File Output'].format.color_mode = 'RGB'
    nodes['File Output'].base_path = '/tmp/%s' % time()
    scene.render.filepath = '/tmp/%s' % time()
    node_tree.links.new(nodes['Render Layers'].outputs['Normal'],
                        nodes['File Output'].inputs['Image'])

    # Select rendering engine based on whether camera or object space is desired
    if camera_space:
        scene.render.engine = 'BLENDER_RENDER'
    else:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 1

    # scene.render.use_antialiasing = False

    # Render
    bpy.ops.render.render(write_still=True)

    # Move from temporary directory
    if not outpath.endswith('.exr'):
        outpath += '.exr'
    move(join(nodes['File Output'].base_path, 'Image0001.exr'), outpath)

    logger.name = logger_name
    logger.info("Normal map of %s rendered through '%s' to %s", obj_names, cam.name, outpath)
    logger.warning("    ..., and the scene node tree has changed")
