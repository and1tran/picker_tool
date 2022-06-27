#!/usr/bin/env python
#SETMODE 777

#----------------------------------------------------------------------------------------#
#------------------------------------------------------------------------------ HEADER --#

"""
:author:
    Andy Tran

:synopsis:
    The enumerator module for the Picker Tool.

:description:
    This module holds the enumerators for the Picker Tool to function. The choices of
    the mirror options, custom shape options, shape precisions, and button attrs are
    a few enums held in this module. Any of the icons also have enums here.

:applications:
    Maya.

:see_also:
    .picker_gui.py
    .picker_gui_utils.py
"""

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- IMPORTS --#

# Default Python Imports
import os
from os.path import expanduser

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- CLASSES --#

class PickerToolEnums(object):

    EXPORT_BTN_ATTRS = ["brush_col", "text", "pos", "set_rect", "sel_objs",
                        "curr_shape", "curr_coords"]
    EXPORT_IMG_ATTRS = ["pos", "filepath"]

    XML_BTN_CATEGORY = "SHAPES"
    XML_IMG_CATEGORY = "IMAGES"
    XML_IMG_PREFIX = "image"
    XML_BTN_PREFIX = "shape"

    SHAPES = ["Rounded Rect", "Rect", "Custom"]
    PRECISIONS = ["Simple (Default)", "Medium", "Exact"]
    PRECISIONS_DICT = {PRECISIONS[0]: 0.1,
                       PRECISIONS[1]: 0.05,
                       PRECISIONS[2]: 0.01}

    MINIMUM_SIZE = 25.0

    USER_DOCS = expanduser("~")
    WORKING_DIR = os.path.dirname(os.path.realpath(__file__))
    TOOL_FOLDER = "picker_tool"
    IMG_FOLDER = "imgs"
    CONFIG_FOLDER = "config"
    LOST_IMAGE = "lost_image.png"

    SCREENSHOT_PREFIX = "screenshot"
    SCREENSHOT_EXT =  "png"

    DEFAULT_TAB_NAME = "default"

    NO_CTRLS_MSG = "No controls set"

    MIRROR_ONS = ["World", "Ref Shape"]
    MIRROR_TYPES = ["Duplicate", "Use Existing"]

    SCENE_BG = "#393939"
    SCENE_LIGHT = "#2f2f2f"
    SCENE_DARK = "#292929"

class PickerIcons(object):

    SAVE_ICON = ":/save.png"
    LOAD_ICON = ":/openScript.png"

    TOGGLE_EDIT_ICON = ":/editRenderPass.png"
    SHOW_SET_ICON = ":/eye.png"
    HIDE_SET_ICON = ":/DeleteHistory.png"

    CREATE_TAB_ICON = ":/newLayerEmpty.png"
    RENAME_TAB_ICON = ":/pencilCursor.png"
    REMOVE_TAB_ICON = ":/delete.png"

    CREATE_BTN_ICON = ":/shelf_modelingToolkit.png"
    UPDATE_BTN_ICON = ":/polyRetopo.png"
    UPDATE_SEL_ICON = ":/polyMerge.png"
    DEL_BTN_ICON = ":/delete.png"
    SCRN_SHOT_ICON = ":/savePaintSnapshot.png"

    MIRROR_ICON = ":/polyFlip.png"
    MIRROR_SET_ICON = ":/polyGear.png"

    ALIGN_X_ICON = ":/alignUMax.png"
    ALIGN_Y_ICON = ":/alignVMin.png"

    REFRESH_NS_ICON = ":/refresh.png"

    MOVE_UP = ":/dollyIn.png"
    MOVE_DOWN = ":/dollyOut.png"

    SET_REF_ICON = ":/CenterPivot.png"
