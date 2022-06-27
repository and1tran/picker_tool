#!/usr/bin/env python
#SETMODE 777

#----------------------------------------------------------------------------------------#
#------------------------------------------------------------------------------ HEADER --#

"""
:author:
    Andy Tran

:synopsis:
    The utility module for the main interface of the Picker Tool.

:description:
    This modules holds the necessary objects to create views, scenes, buttons, and
    image graphics elements by extending PySide2 widgets.

    The scenes are implemented on the main window's tabs, with views framing the scenes.
    Here is where the controls for navigating and updating the graphics scene, views,
    and its items. The mousePressEvents and keyPressEvents are reimplemented within the
    GraphicsView class.

    The Picker Preview classes are the view and scene on the main window giving
    the user a preview to what their button would look like if implemented.

    The behavior to how buttons update themselves are here. Pixmaps objects, used for
    images are here too.

    The logic to select objects in Maya are within the GraphicsButton class.

    Other useful Picker Tool elements are here such as verifying selections for Maya
    and GUI separators.

:applications:
    Maya.

:see_also:
    .picker_gui.py
    .picker_enums.py
"""

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- IMPORTS --#

# Default Python Imports
from PySide2 import QtWidgets, QtGui, QtCore
import math
import maya.cmds as cmds

from .picker_enums import PickerToolEnums

#----------------------------------------------------------------------------------------#
#--------------------------------------------------------------------------- FUNCTIONS --#

def get_selected_items(multi=False, type=["transform"]):
    """
    Get and verify there is only one valid selection out of the selected items

    :param multi: Whether we want one item in the return list or multiple.
    :type: bool

    :param type: What types we want from the Maya scene.
    :type: list

    :return: Returns a list of selected objects. Still return a list if we only want
             one obj.
    :type: list
    """
    sel_items = cmds.ls(selection=True, type=type)
    if not sel_items:
        valid_types_str = ", ".join(type)
        print("No valid items selected. Please select of type: %s" % valid_types_str)
        return None

    # If we want multiple selected items returned.
    if multi:
        return_list = sel_items

    # Only one will be used.
    else:
        if len(sel_items) > 1:
            print("Too many selected")
            return None
        else:
            return_list = sel_items

    return return_list

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- CLASSES --#


class GraphicsScene(QtWidgets.QGraphicsScene):
    """
    The main Graphics Scene implemented in the Picker Tool's tabs.
    """
    def __init__(self, parent=None):
        """
        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget
        """
        super().__init__(parent)

        # Tab specific attrs.
        self.ref_item = None

        # Displays settings.
        self.gridSize = 20
        self.gridSquares = 4

        self._color_background = QtGui.QColor(PickerToolEnums.SCENE_BG)
        self._color_light = QtGui.QColor(PickerToolEnums.SCENE_LIGHT)
        self._color_dark = QtGui.QColor(PickerToolEnums.SCENE_DARK)
        self.setBackgroundBrush(self._color_background)

        self._pen_light = QtGui.QPen(self._color_light)
        self._pen_light.setWidth(1)
        self._pen_dark = QtGui.QPen(self._color_dark)
        self._pen_dark.setWidth(2)

        self.scene_width, self.scene_height = 9000, 9000
        # Double slash means giving back an integer.
        self.setSceneRect(-self.scene_width // 2, -self.scene_height // 2,
                          self.scene_width,
                          self.scene_height)

    def drawBackground(self, painter, rect):
        """
        Reimplemented by drawing the grid and background of the graphics scene.
        """
        super().drawBackground(painter, rect)

        # Here we create our grid
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        top = int(math.floor(rect.top()))
        bottom = int(math.ceil(rect.bottom()))

        first_left = left - (left % self.gridSize)
        first_top = top - (top % self.gridSize)

        # Compute all lines to be drawn.
        lines_light, lines_dark = [], []
        for x in range(first_left, right, self.gridSize):
            if x % (self.gridSize*self.gridSquares) != 0:
                lines_light.append(QtCore.QLine(x, top, x, bottom))
            else:
                lines_dark.append(QtCore.QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self.gridSize):
            if y % (self.gridSize*self.gridSquares) != 0:
                lines_light.append(QtCore.QLine(left, y, right, y))
            else:
                lines_dark.append(QtCore.QLine(left, y, right, y))

        # Draw the lines
        painter.setPen(self._pen_light)
        for line in lines_light:
            painter.drawLine(line)

        # Draw the dark lines
        painter.setPen(self._pen_dark)
        for line in lines_dark:
            painter.drawLine(line)

    def mouseReleaseEvent(self, event):
        """
        Reimplemented the mouse release event. The left button is the main one to
        change.
        """
        if event.button() == QtCore.Qt.LeftButton:
            self.highlight_items()
            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def highlight_items(self):
        """
        Highlight the selected items visually. If it's a pixmap, skip it.
        """
        sel_items = self.selectedItems()
        scene_items = self.items()
        for item in scene_items:
            if isinstance(item, GraphicsPixmap):
                continue
            if item in sel_items:
                item.highlight_button(True)
            else:
                item.highlight_button(False)

        self.update()

    def contextMenuEvent(self, event):
        """
        Reimplemented the contextMenuEvent, displaying menus on right-clicks when over
        items, not over items, and over pixmaps.
        """
        over_item = self.itemAt(event.scenePos(), QtGui.QTransform())
        clicked_scene_pos = event.scenePos()

        # Make all variables so after checking if we're over an item, then we can check
        # what action we got.
        new_btn_act = None
        replace_pixmap_act = None
        upd_btn_act = None
        upd_sel_act = None
        del_btn_act = None
        brg_fwd_act = None
        send_bwd_act = None
        align_x_act = None
        align_y_act = None
        set_ref_act = None
        cl_ref_act = None
        mir_btn_act = None

        contextMenu = QtWidgets.QMenu()

        # Context menu for pixmaps.
        if isinstance(over_item, GraphicsPixmap):
            replace_pixmap_act = contextMenu.addAction("Replace Image")

        # Context menu when over an item.
        elif over_item:
            # Adding a section to the start of context menu is bugged.
            # contextMenu.addSection("Button")
            upd_btn_act = contextMenu.addAction("Update Button")
            upd_sel_act = contextMenu.addAction("Update Button Selection")
            del_btn_act = contextMenu.addAction("Delete")
            contextMenu.addSeparator()
            brg_fwd_act = contextMenu.addAction("Bring Forward")
            send_bwd_act = contextMenu.addAction("Send Backward")
            align_x_act = contextMenu.addAction("Align X")
            align_y_act = contextMenu.addAction("Align Y")
            set_ref_act = contextMenu.addAction("Set as Ref Button")
            cl_ref_act = contextMenu.addAction("Clear Ref Button")
            mir_btn_act = contextMenu.addAction("Mirror")

        # Context menu when over an empty space.
        else:
            new_btn_act = contextMenu.addAction("New Button")
            cl_ref_act = contextMenu.addAction("Clear Ref Button")

        action = contextMenu.exec_(event.screenPos())

        # Call the main window's functions to execute the actions.
        if not action:
            return None
        elif action == replace_pixmap_act:
            self.parent().replace_pixmap(pixmap_item=over_item)
        elif action == upd_btn_act:
            self.parent().update_btn(items=[over_item])
        elif action == upd_sel_act:
            self.parent().update_btn_selection(items=[over_item])
        elif action == del_btn_act:
            self.parent().delete_btn(items=[over_item])
        elif action == brg_fwd_act:
            self.parent().bring_forward()
        elif action == send_bwd_act:
            self.parent().send_backward()
        elif action == align_x_act:
            self.parent().align_by_x()
        elif action == align_y_act:
            self.parent().align_by_y()
        elif action == set_ref_act:
            self.parent().set_ref_item(item=[over_item])
        elif action == cl_ref_act:
            self.parent().clear_ref_item()
        elif action == mir_btn_act:
            self.parent().mirror_sel_btns()
        elif action == new_btn_act:
            self.parent().create_btn(set_pos=clicked_scene_pos)


class GraphicsView(QtWidgets.QGraphicsView):
    """
    The main Graphics View implemented in the Picker Tool's tabs.
    """
    def __init__(self, gr_scene, parent=None, main_wnd_ref=None):
        """
        :param gr_scene: The graphics scene to view in the graphics view.
        :type: GraphicsScene

        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget

        :param main_wnd_ref: The main window the graphics view is within, we can't use
                             the parent b/c it's added to the tab widget.
        :type: QtWidgets.QMainWindow
        """
        super().__init__(scene=gr_scene, parent=parent)

        self.main_wnd_ref = main_wnd_ref

        self.gr_scene = gr_scene
        self.setScene(self.gr_scene)

        self.namespace = None

        self.init_gui()

        # Attributes for zoom
        self.zoomInFactor = 1.25
        self.zoomClamp = True
        self.zoom = 5
        self.zoomStep = 1
        self.zoomRange = [0, 500]

        # Attributes for selecting objects.
        self.initial_mouse_pos = None
        self.old_sel_items = []
        self.drag = None

    def init_gui(self):
        """
        GUI elements like hiding scroll bars and render hints.
        """
        self.setRenderHints(QtGui.QPainter.Antialiasing |
                            QtGui.QPainter.HighQualityAntialiasing |
                            QtGui.QPainter.TextAntialiasing |
                            QtGui.QPainter.SmoothPixmapTransform)

        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)

    def keyPressEvent(self, event):
        """
        Reimplemented the keyPressEvent to focus on selected items or the scene's center
        when the "F" key is pressed. All other events are regular.

        :param event: The event from a key press.
        :type: QtCore.QEvent
        """
        if event.key() == QtCore.Qt.Key_F and self.scene().selectedItems():
            new_center = self.main_wnd_ref.get_average_coord(self.scene().selectedItems())
            self.centerOn(new_center)
        elif event.key() == QtCore.Qt.Key_F:
            self.centerOn(0.0, 0.0)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """
        Reimplemented the mousePressEvent to implement a middle mouse drag and selection
        like toggle, add, and unselect items.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        self.initial_mouse_pos = event.pos()

        self.drag = False

        if event.button() == QtCore.Qt.MiddleButton:
            self.middleMouseButtonPress(event)

        if event.button() == QtCore.Qt.LeftButton and \
            event.modifiers() == (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier):
            self.ctrl_shift_left_click(event)

        elif event.button() == QtCore.Qt.LeftButton and \
                                            event.modifiers() == QtCore.Qt.ShiftModifier:
            self.shift_left_click(event)

        elif event.button() == QtCore.Qt.LeftButton and \
                                        event.modifiers() == QtCore.Qt.ControlModifier:
            self.ctrl_click(event)

        elif event.button() == QtCore.Qt.LeftButton:
            self.leftMouseButtonPress(event)

        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Reimplemented the mouseReleaseEvent to release the middle mouse drag and
        implement the selection.

        :param event: The event from a mouse button release.
        :type: QtCore.QEvent
        """
        if event.button() == QtCore.Qt.MiddleButton:
            self.middleMouseButtonRelease(event)
        elif event.button() == QtCore.Qt.LeftButton:
            self.leftMouseButtonRelease(event)
        else:
            super().mouseReleaseEvent(event)

    def middleMouseButtonPress(self, event):
        """
        PySide2 has a middle mouse drag, but needs a left click to drag after setting to
        a drag. So make a release event to let go of the middle mouse drag then make a
        fake left click event. So when the user middle mouse clicks, it will be set to
        drag.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        releaseEvent = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonRelease,
                                         event.localPos(),
                                         event.screenPos(), QtCore.Qt.LeftButton,
                                         QtCore.Qt.NoButton,
                                         event.modifiers())
        super().mouseReleaseEvent(releaseEvent)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        fakeEvent = QtGui.QMouseEvent(event.type(), event.localPos(), event.screenPos(),
                                      QtCore.Qt.LeftButton,
                                      event.buttons() | QtCore.Qt.LeftButton,
                                      event.modifiers())
        super().mousePressEvent(fakeEvent)

    def middleMouseButtonRelease(self, event):
        """
        So when the user releases middle mouse, it will send a left click to release
        the drag.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        fakeEvent = QtGui.QMouseEvent(event.type(), event.localPos(), event.screenPos(),
                                      QtCore.Qt.LeftButton,
                                      event.buttons() ^ QtCore.Qt.LeftButton,
                                      event.modifiers())
        super().mouseReleaseEvent(fakeEvent)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)

    def getItemAtClick(self, event):
        """
        Return the object on clicked and release mouse button. If it's a pixmap, then
        we don't return b/c this function is primarily used to highlight selected items.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        pos = event.pos()
        obj = self.itemAt(pos)

        # If the object is a pixmap, don't return it b/c pixmaps can't be highlighted.
        if isinstance(obj, GraphicsPixmap):
            return None
        return obj

    def leftMouseButtonPress(self, event):
        """
        Set the mode to replace and set the necessary flags for selection upon release.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        self.mode = "replace"
        item = self.getItemAtClick(event)

        # If we are over an item, then we're dragging, but if we aren't then no drag.
        if item:
            self.drag = True
        else:
            self.drag = False

        # If the item is a pixmap, don't do anything, otherwise use the regular event.
        if isinstance(item, GraphicsPixmap):
            pass
        else:
            super().mousePressEvent(event)

    def shift_left_click(self, event):
        """
        Set the mode to toggle upon shift-clicking.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        self.mode = "toggle"
        # Getting the drag needs the parent's mousePressEvent, but breaks the selection.
        # super().mousePressEvent(event)

    def ctrl_click(self, event):
        """
        Set the mode to subtract upon ctrl-clicking.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        self.mode = "subtract"
        # Getting the drag needs the parent's mousePressEvent, but breaks the selection.
        # super().mousePressEvent(event)

    def ctrl_shift_left_click(self, event):
        """
        Set the mode to adding upon ctrl-shift-clicking.

        :param event: The event from a mouse button.
        :type: QtCore.QEvent
        """
        self.mode = "add"
        # Getting the drag needs the parent's mousePressEvent, but breaks the selection.
        # super().mousePressEvent(event)

    def leftMouseButtonRelease(self, event):
        """
        Determine whether the mouse was dragged, then create the new selected items.
        Evaluate the new selected items, alter the selected items, highlight the
        selected items and select the items in Maya.

        :param event: The event from a mouse button release.
        :type: QtCore.QEvent
        """
        # Determine if the mouse was dragged.
        if event.pos() != self.initial_mouse_pos:

            # If there was a drag, then keep the old selection and add the new item that
            # was dragged.
            if self.drag:
                over_item = [self.getItemAtClick(event)]
                sel_items = list(set(self.old_sel_items).union(set(over_item)))

            # Otherwise, there was no drag so we were over no item upon clicking, which
            # means we're dragging but not moving an item. This is a new selection.
            else:
                sel_paint_path = self.rubberBandRect()
                sel_items = self.items(sel_paint_path, QtCore.Qt.IntersectsItemShape)

        # The mouse wasn't dragged so we're just clicking on a new item.
        else:
            sel_items = [self.getItemAtClick(event)]
            self.drag = False

        # Evaluate the new items based on the mode and select the items.
        self.evaluate_temp_items(sel_items)
        self.select_items()

        # Clear the selected items in Maya then select the current objs.
        self.clear_maya_select()
        self.select_items_maya()

        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """
        Calculate the amount of zoom and scale the viewport to that amount.

        :param event: The event from a mouse wheel spin.
        :type: QtCore.QEvent
        """
        # Calculate our zoom factor.
        zoomOutFactor = 1 / self.zoomInFactor

        # Calculate zoom
        if event.angleDelta().y() > 0:
            zoomFactor = self.zoomInFactor
            self.zoom += self.zoomStep
        else:
            zoomFactor = zoomOutFactor
            self.zoom -= self.zoomStep

        clamped = False
        if self.zoom < self.zoomRange[0]: self.zoom, clamped = self.zoomRange[0], True
        if self.zoom > self.zoomRange[1]: self.zoom, clamped = self.zoomRange[1], True

        # Set the scene scale.
        if not clamped or self.zoomClamp is False:
            self.scale(zoomFactor, zoomFactor)

    def select_items(self):
        """
        Selects the item in the graphics scene.
        """
        all_items = self.items()
        for item in all_items:
            if item in self.old_sel_items:
                item.setSelected(True)
            else:
                item.setSelected(False)

    def evaluate_temp_items(self, changed_items):
        """
        Based on the mode set, Evaluates the items to edit our selected items list.

        :param changed_items: List of new items we clicked or dragged over.
        :return: list
        """
        # Left-click will just set to replace and add when not dragging.
        if self.mode == "replace":
            if self.drag:
                pass
            else:
                self.old_sel_items.clear()
            self.old_sel_items = list(set(self.old_sel_items).union(set(changed_items)))

        # Shift-left-clicking will toggle the new items. So loop through the items and
        # deselect selected items and select any unselected items. Evaluate by putting
        # the items into an add and subtract list then update the old_sel items list.
        elif self.mode == "toggle":
            add_items = []
            subtract_items = []
            for item in changed_items:
                if item in self.old_sel_items:
                    subtract_items.append(item)
                else:
                    add_items.append(item)

            self.old_sel_items = list(set(self.old_sel_items).union(set(add_items)))
            self.old_sel_items = list(
                set(self.old_sel_items).difference(set(subtract_items)))

        # Ctrl-click will deselect all items.
        elif self.mode == "subtract":
            self.old_sel_items = list(
                set(self.old_sel_items).difference(set(changed_items)))

        # Ctrl-shift-click will add all items.
        elif self.mode == "add":
            self.old_sel_items = list(set(self.old_sel_items).union(set(changed_items)))

    def clear_maya_select(self):
        """
        Clears the selection in Maya.
        """
        cmds.select(clear=True)

    def select_items_maya(self):
        """
        Selects the items in Maya.
        """
        all_items = self.items()

        # Create the base string using the namespace.
        if self.namespace:
            base_str = self.namespace + ":"
        else:
            base_str = ""

        for item in all_items:

            # If it is a pixmap, skip.
            if isinstance(item, GraphicsPixmap):
                continue

            # If the item is selected, iterate through the selected objects and try to
            # select it. Otherwise print saying what it's trying to select.
            if item.isSelected():
                sel_objs = item.sel_objs
                for obj in sel_objs:
                    try:
                        obj_name = base_str + obj
                        cmds.select(obj_name, add=True)
                    except ValueError:
                        print("Can't select: \"%s\"" % obj_name)


class PickerPreviewGraphicsScene(QtWidgets.QGraphicsScene):
    """
    Picker Preview separated. Doesn't need all the functions of a main graphics scene.
    """
    def __init__(self, parent=None):
        """
        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget
        """
        super().__init__(parent)

        # Settings
        self._color_background = QtGui.QColor(PickerToolEnums.SCENE_BG)

        self.scene_width, self.scene_height = 500, 500
        self.setSceneRect(-250, -250, self.scene_width, self.scene_height)

        self.setBackgroundBrush(self._color_background)


class PickerPreviewGraphicsView(QtWidgets.QGraphicsView):
    """
    Picker Preview separated. Doesn't need all the functions of a main graphics view.
    """
    def __init__(self, gr_scene, parent=None):
        """
        :param gr_scene: The Picker Preview scene.
        :type: PickerPreviewGraphicsScene

        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget
        """
        super().__init__(scene=gr_scene, parent=parent)
        self.gr_scene = gr_scene
        self.setScene(self.gr_scene)
        self.init_gui()

        self.setFixedSize(200, 200)

    def init_gui(self):
        """
        GUI elements like hiding scroll bars and render hints.
        """
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.HighQualityAntialiasing | QtGui.QPainter.TextAntialiasing |
                            QtGui.QPainter.SmoothPixmapTransform)

        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)


class GraphicsPixmap(QtWidgets.QGraphicsPixmapItem):
    """
    Graphics Pixmap item. This will hold the image and its pixmap attrs.
    """
    def __init__(self, parent=None, image=None, good_img=True):
        """
        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget

        :param image: The image file path.
        :type: str

        :param good_img: Whether the file path is good or not.
        :type: bool
        """
        super().__init__(parent)

        # This bool is for importing images and acknowledging if the new pixmap item
        # is pointing to a good file path. If not, then it will use a backup image.
        self.good_img = good_img

        pixmap = QtGui.QPixmap(image)
        self.setPixmap(pixmap)

        self.file_path = image

        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)

    def set_edit_mode(self, editable=True):
        """
        This will set the pixmap item to be selectable and movable.

        :param editable: The flag to set the pix map.
        :type: bool
        """
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, editable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, editable)

    def highlight_button(self, highlight=None):
        """
        This is when the graphics buttons are highlighted, a pixmap will skip this.
        """
        pass


class GraphicsButton(QtWidgets.QGraphicsItem):
    """
    Graphics Button for the picker preview and objects in the main scene tabs.
    """
    def __init__(self, parent=None, main=False, sel_list=None, **kwargs):
        """
        :param parent: The parent widget it will be attached to.
        :type: QtWidgets.QWidget

        :param main: Whether this item is in the picker preview or a main graphics scene
                     in a tab. This sets flags b/c the picker preview has flags off.
        :type: bool

        :param sel_list: The list of objects this button selects.
        :type: list

        :param kwargs: The dictionary for the graphics item elements, it will look like:
                       {"brush_col": QtGui.QColor,
                        "text": str,
                        "set_rect": QtCore.QRectF,
                        "curr_shape": "Rounded Rect",
                        "curr_coords": [QtPointF, QtPointF,...],
                        "set_polygon": QtGui.QPolygonF}
        :type: dict
        """
        super().__init__(parent)

        if sel_list:
            self.sel_objs = sel_list
        else:
            self.sel_objs = []

        btn_attrs = PickerToolEnums.EXPORT_BTN_ATTRS

        self.brush_col = kwargs.setdefault(btn_attrs[0], QtGui.QBrush(QtCore.Qt.black))
        self.pen_col = QtGui.QPen(QtGui.QColor(10, 10, 10, 255))
        self.brush_hl = QtGui.QBrush(QtGui.QColor(255, 255, 255, 255))
        self.pen_hl = QtGui.QPen(QtGui.QColor(80, 150, 60, 255))

        self.brush = self.brush_col
        self.pen = self.pen_col
        self.text = kwargs.setdefault(btn_attrs[1], "")
        self.set_rect = kwargs.setdefault(btn_attrs[3], QtCore.QRect(0, 0, 5, 5))

        self.minimum_size = PickerToolEnums.MINIMUM_SIZE

        # TODO: Change these to not be hard coded or default to a centralized data file.
        self.curr_shape = kwargs.setdefault(btn_attrs[5], PickerToolEnums.SHAPES[0])
        self.curr_coords = kwargs.setdefault(btn_attrs[6],
                                             [[0.0, 0.0],
                                              [self.minimum_size, 0.0],
                                              [self.minimum_size, self.minimum_size],
                                              [0.0, self.minimum_size]]
                                             )
        default_coords = []
        for creation_pt in self.curr_coords:
            default_coords.append(QtCore.QPointF(creation_pt[0], creation_pt[1]))

        self.set_polygon = kwargs.setdefault("set_polygon",
                                             QtGui.QPolygonF(default_coords))

        if main:
            self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable |
                          QtWidgets.QGraphicsItem.ItemIsMovable)

    def boundingRect(self, new_rect=None):
        """
        Reimplement the virtual function to a variable a malleable rect.
        """
        return self.set_rect

    def shape(self):
        """
        Reimplement the virtual function to a variable we can swap around.

        IMPORTANT: The shape sets the selectable area of the item. This is important to
        keep the shape consistent with what is displayed.
        """
        path = QtGui.QPainterPath()
        path.addPolygon(self.set_polygon)
        return path

    def paint(self, painter, option, widget):
        """
        Reimplement the virtual function to paint the selected graphics item. Depending
        on when the element was painted is the order of the elements. Which is why the
        text is painted last.
        """
        rectF = self.set_rect

        painter.setBrush(self.brush)

        # Might want to try to implement some way to change the text color but not pen.
        painter.setPen(self.pen)

        # Draw the graphics item based on which shape is selected.
        if self.curr_shape == PickerToolEnums.SHAPES[0]:
            painter.drawRoundedRect(rectF, 7, 7)
        elif self.curr_shape == PickerToolEnums.SHAPES[1]:
            painter.drawRect(rectF)
        elif self.curr_shape == PickerToolEnums.SHAPES[2]:
            new_polygon = self.set_polygon
            painter.drawPolygon(new_polygon)
        else:
            painter.drawRect(rectF)

        # Text is painted last to be placed on top.
        painter.drawText(rectF.x(), rectF.y(), rectF.width(), rectF.height(),
                         QtCore.Qt.AlignCenter, self.text)

    def update_polygon(self, new_polygon_coords=None):
        """
        Update the graphic shape's polygon by calculating the current amount of scaling
        to the x and y based on the bounding rect's dimensions from the minimum size.

        :param new_polygon_coords: A list of lists holding the new polygon's coords.
        :type: list
        """
        # If this is not a custom shape then use the default
        if not self.curr_shape == PickerToolEnums.SHAPES[2]:
            rect = self.set_rect
            QtGui.QPolygonF(rect)
            new_polygon = QtGui.QPolygonF(rect)
            self.set_polygon = new_polygon
            self.update()

        # Else create the polygon with the coords and make it the shape too.
        else:

            # If we got no coords passed, then use the class's old coords.
            if not new_polygon_coords:
                if not self.curr_coords:
                    return None
                new_polygon_coords = self.curr_coords

            # Get the current bounding rect.
            rectF = self.set_rect
            curr_width = rectF.width()
            curr_height = rectF.height()

            # Calculate how much the factor multiplies by the minimum size.
            scale_width_factor = curr_width / self.minimum_size
            scale_height_factor = curr_height / self.minimum_size

            # Apply the scale to each point.
            scaled_coords = []
            for curr_coords in new_polygon_coords:
                x_scaled = curr_coords[0] * scale_width_factor
                y_scaled = curr_coords[1] * scale_height_factor
                scaled_coords.append(QtCore.QPointF(x_scaled, y_scaled))

            # Create the new polygon and set the button's polygon and coords.
            new_polygon = QtGui.QPolygonF(scaled_coords)
            self.curr_coords = new_polygon_coords
            self.set_polygon = new_polygon
            self.update()

    def update_curr_shape(self, new_shape=None):
        """
        Updates the curr_shape and updates the shape.

        :param new_shape: The new_shape mode
        :type: QtGui.QPolygonF
        """
        if not new_shape:
            return None

        self.curr_shape = new_shape
        self.update_polygon()

    def update_bounding_rect(self, new_rect=None):
        """
        Updates the button's bounding box.

        :param new_rect: The new rect we're applying.
        :type: QtCore.QRect
        """
        if not new_rect:
            return None

        self.set_rect = new_rect
        self.update_polygon()
        self.update()

    def update_text(self, text=None):
        """
        Update the button's text.

        :param text: The new text we're applying.
        :type: str
        """
        if text is None:
            return None

        self.text = text
        self.update()

    def update_brush_color(self, color=None):
        """
        Update the text on the graphic item.

        :param color: The new rect we're applying.
        :type: QtCore.QColor
        """
        if not color:
            return None

        self.brush_col = color
        self.brush = self.brush_col
        self.update()

    def update_sel_list(self, new_sel=None):
        """
        Updates the graphic button's selection list.

        :param new_sel: The new selection.
        :type: list
        """
        if not new_sel:
            return None

        self.sel_objs = new_sel

    def highlight_button(self, hl=False):
        """
        Update the button's brush and pen to highlight mode or not.
        """
        if hl is True:
            self.pen = self.pen_hl
            self.brush = self.brush_hl
        else:
            self.pen = self.pen_col
            self.brush = self.brush_col


class HLine(QtWidgets.QFrame):
    """
    Creates an instance of a horizontal line
    """
    def __init__(self):
        QtWidgets.QFrame.__init__(self)

    def make_line(self):
        """
	    Runs all the necessary commands to create a horizontal line that can be displayed
	    on a GUI.

        :return: HLine widget object
        """
        line = QtWidgets.QLabel()
        line.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Plain)
        return line


class VLine(QtWidgets.QFrame):
    """
    Creates an instance of a vertical line
    """
    def __init__(self):
        QtWidgets.QFrame.__init__(self)

    def make_line(self):
        """
        Runs all the necessary commands to create a vertical line that can be displayed
        on a GUI.

        :return: VLine widget object
        """
        line = QtWidgets.QLabel()
        line.setFrameStyle(QtWidgets.QFrame.VLine | QtWidgets.QFrame.Plain)
        return line

