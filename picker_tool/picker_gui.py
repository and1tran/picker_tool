#!/usr/bin/env python
#SETMODE 777

#----------------------------------------------------------------------------------------#
#------------------------------------------------------------------------------ HEADER --#

"""
:author:
    Andy Tran

:synopsis:
    The main interface and controller of the Picker Tool.

:description:
    This module populates the Picker Tool window and connects the buttons to the
    functions of the GUI utils and Maya. The PickerWindow is the main window the rigger
    will interact with to create pickers, and the animators can use as an animation tool.

    The logic for saving out and loading the picker tools to XML files are here. The
    functions for taking screenshots and how it's saved is here too.

    Additional Dialogs are at the bottom to give the user options to change the behavior
    of saving out pickers and mirroring.

:applications:
    Maya.

:see_also:
    .picker_enums.py
    .picker_gui_utils.py
"""

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- IMPORTS --#

# Default Python Imports
from PySide2 import QtGui, QtWidgets, QtCore
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance
import copy
import maya.cmds as cmds
import maya.mel as mel
import os
from xml.dom import minidom
import xml.etree.ElementTree as et

# Tool Imports
from .picker_gui_utils import (GraphicsScene, GraphicsView,
                               GraphicsButton, GraphicsPixmap,
                               PickerPreviewGraphicsScene,
                               PickerPreviewGraphicsView,
                               HLine, VLine,
                               get_selected_items)
from .picker_enums import PickerToolEnums, PickerIcons

#----------------------------------------------------------------------------------------#
#--------------------------------------------------------------------------- FUNCTIONS --#

def get_maya_window():
    """
    This gets a pointer to the Maya window.
    :return: A pointer to the Maya window.
    :type: pointer
    """
    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(maya_main_window_ptr), QtWidgets.QWidget)

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- CLASSES --#

class PickerWindow(QtWidgets.QMainWindow):
    """
    The Main Window of the Picker Tool. 
    """
    def __init__(self, edit_mode=True):
        QtWidgets.QMainWindow.__init__(self, parent=get_maya_window())

        self.edit_mode = edit_mode

        self.window_widgets = []

        self.selected_items = None

        self.tabs_dict = {}
        self.curr_scene = None

        self.curr_ns = None

        # Mirror Dialog holds the mirror settings.
        self.mirror_settings = MirrorSettingsDialog(self)


    def init_gui(self):
        """
        Creates the GUI and shows the GUI to the user.
        """
        # Create the menu bar.
        self.create_menu_bar()

        main_hb = QtWidgets.QHBoxLayout()

        # Create the tab section.
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setMinimumSize(500, 700)
        self.create_tab(PickerToolEnums.DEFAULT_TAB_NAME)
        self.tab_widget.currentChanged[int].connect(self.tab_changed)
        main_hb.addWidget(self.tab_widget)

        # Create the settings section.
        settings_layout = self.create_settings_layout()
        main_hb.addLayout(settings_layout)

        # Create a QWidget to use as the central widget.
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(main_hb)
        self.setCentralWidget(central_widget)

        # Set the main hb properties.
        main_hb.setContentsMargins(0, 0, 0, 0)
        main_hb.setSpacing(1)

        # Set the edit mode after all the widgets and values have been created.
        self.set_edit_mode()

        # Configure the window.
        # Use "self.setFixedSize(main_hb.sizeHint())" to figure out the minimum sizes
        minimum_size = {"x": 997, "y": 726}

        self.setGeometry(100, 200, minimum_size["x"], minimum_size["y"])
        # self.setMinimumSize(minimum_size["x"], minimum_size["y"])
        self.setWindowTitle("Picker Tool")
        self.show()

        # For the first time, center on the center on the main graphics view and the
        # picker preview.
        self.curr_scene.views()[0].centerOn(0.0, 0.0)
        preview_prev_center = self.get_center(self.pp_item)
        self.pick_prvw_view.centerOn(preview_prev_center)

    def create_menu_bar(self):
        """
        Creates the menu bar.
        """
        main_menu = QtWidgets.QMenuBar()

        # Create the file menu on the main menu.
        self.create_file_menu(main_menu)

        # Create the edit menu on the main menu.
        self.create_edit_menu(main_menu)

        # Namespace.
        self.create_namespace_menu(main_menu)

        self.setMenuBar(main_menu)

    def create_file_menu(self, menu_bar=None):
        """
        Creates the file menu on the menu bar.

        :param menu_bar: The main menu bar we're adding to.
        :type: QtWidgets.QMenuBar
        """
        if not menu_bar:
            return None

        # File menu.
        file_menu = menu_bar.addMenu("File")

        # Save As.
        save_act = QtWidgets.QAction("Save As...", self)
        save_icon = QtGui.QIcon(PickerIcons.SAVE_ICON)
        save_act.setIcon(save_icon)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_as_clicked)
        file_menu.addAction(save_act)

        # Load.
        load_act = QtWidgets.QAction("Load", self)
        load_icon = QtGui.QIcon(PickerIcons.LOAD_ICON)
        load_act.setIcon(load_icon)
        load_act.setShortcut("Ctrl+O")
        load_act.triggered.connect(self.load_xml_file)
        file_menu.addAction(load_act)

        # Close the window.
        exit_act = QtWidgets.QAction("Exit", self)
        exit_act.setShortcut("Ctrl+W")
        exit_act.triggered.connect(self.exit_window)
        file_menu.addAction(exit_act)

    def save_as_clicked(self):
        """
        "Save as" will call a dialog to emit a signal, or not, and call self.save_xml_file
        if we got the "save_as_clicked" signal.
        """
        save_tab_dialog = SaveTabsDialog()
        save_tab_dialog.init_gui(self.tab_widget)
        save_tab_dialog.save_as_clicked.connect(self.save_xml_file)

    def save_xml_file(self, tabs):
        """
        Opens a dialog to ask for a file path. Then saves out an xml file for all the
        desired tabs.

        :return: The file exported.
        :type: str
        """
        # Prompt the user starting at their home directory.
        filename, ffilter = QtWidgets.QFileDialog.getSaveFileName(caption="Save File",
                                                    dir=PickerToolEnums.USER_DOCS,
                                                    filter="XML files (*.xml)")

        # If we didn't get a filename, then do nothing.
        if not filename:
            return None

        export_shape_attrs = PickerToolEnums.EXPORT_BTN_ATTRS
        export_img_attrs = PickerToolEnums.EXPORT_IMG_ATTRS

        # Make an XML document and create the root element.
        xml_doc = minidom.Document()
        root = xml_doc.createElement("root")
        xml_doc.appendChild(root)

        # Get the tabs onto the doc.
        for tab_index in tabs:

            # Create the tab element.
            tab_name = self.tab_widget.tabText(tab_index)
            tab_element = xml_doc.createElement(tab_name)
            root.appendChild(tab_element)

            # Get the graphics items.
            tab_scene = self.tabs_dict[tab_index]
            gr_items = tab_scene.items()

            # Make separate elements splitting shapes and images.
            shape_element = xml_doc.createElement(PickerToolEnums.XML_BTN_CATEGORY)
            tab_element.appendChild(shape_element)
            img_element = xml_doc.createElement(PickerToolEnums.XML_IMG_CATEGORY)
            tab_element.appendChild(img_element)

            shape_counter = 1
            img_counter = 1
            for gr_item in gr_items:

                # Saving out a Pixmap item is different, going into the image element.
                if isinstance(gr_item, GraphicsPixmap):
                    image_str = "%s_%02d" % (PickerToolEnums.XML_IMG_PREFIX, img_counter)

                    pix_element = xml_doc.createElement(image_str)
                    img_element.appendChild(pix_element)

                    # Iterate through the attrs for imgs.
                    for attr in export_img_attrs:

                        # Save the position of the image in the graphics scene. This is
                        # the top left corner and its z value.
                        if attr == export_img_attrs[0]:
                            pos_element = xml_doc.createElement(
                                                    PickerToolEnums.EXPORT_IMG_ATTRS[0])
                            pix_element.appendChild(pos_element)
                            save_pos = gr_item.scenePos()
                            save_z = gr_item.zValue()
                            pos_element.setAttribute("x", "%.2f" % save_pos.x())
                            pos_element.setAttribute("y", "%.2f" % save_pos.y())
                            pos_element.setAttribute("z", "%.2f" % save_z)

                        # Save the filepath of the image as an attribute.
                        if attr == export_img_attrs[1]:
                            pixmap_file = gr_item.file_path
                            pix_element.setAttribute(PickerToolEnums.EXPORT_IMG_ATTRS[1],
                                                     pixmap_file)

                    img_counter += 1

                # Save out graphics buttons.
                elif isinstance(gr_item, GraphicsButton):
                    button_str = "%s_%02d" % (PickerToolEnums.XML_BTN_PREFIX,
                                                 shape_counter)

                    gr_item_element = xml_doc.createElement(button_str)
                    shape_element.appendChild(gr_item_element)

                    # Export the attributes of the graphics shapes.
                    for attr in export_shape_attrs:

                        # The brush will save into RGB in the 0-255 range.
                        if attr == export_shape_attrs[0]:
                            brush_element = xml_doc.createElement(export_shape_attrs[0])
                            gr_item_element.appendChild(brush_element)
                            brush_col_rgb = gr_item.brush_col.color().getRgb()
                            brush_element.setAttribute("R", "%i" % brush_col_rgb[0])
                            brush_element.setAttribute("G", "%i" % brush_col_rgb[1])
                            brush_element.setAttribute("B", "%i" % brush_col_rgb[2])

                        # Make text its own element b/c of future expansion to customize
                        # text, like font, size, color.
                        elif attr == export_shape_attrs[1]:
                            save_text = gr_item.text
                            text_element = xml_doc.createElement(export_shape_attrs[1])
                            gr_item_element.appendChild(text_element)
                            text_element.setAttribute(export_shape_attrs[1],
                                                      str(save_text))

                        # Export the x, y, and z value position.
                        elif attr == export_shape_attrs[2]:
                            pos_element = xml_doc.createElement(export_shape_attrs[2])
                            gr_item_element.appendChild(pos_element)
                            save_pos = gr_item.scenePos()
                            save_z = gr_item.zValue()
                            pos_element.setAttribute("x", "%.2f" % save_pos.x())
                            pos_element.setAttribute("y", "%.2f" % save_pos.y())
                            pos_element.setAttribute("z", "%.2f" % save_z)

                        # The bounding rect is still necessary.
                        elif attr == export_shape_attrs[3]:
                            set_rect_element = xml_doc.createElement(
                                                                    export_shape_attrs[3])
                            gr_item_element.appendChild(set_rect_element)
                            save_rect = gr_item.boundingRect()
                            set_rect_element.setAttribute("width", "%d" %
                                                            save_rect.width())
                            set_rect_element.setAttribute("height", "%d" %
                                                            save_rect.height())

                        # The selected objects can just be an attribute, a string.
                        # Looks like: "nurbsCurve1, l_arm_CC, nurbsCurve3,..."
                        elif attr == export_shape_attrs[4]:
                            export_str = ", ".join(str(obj) for obj in gr_item.sel_objs)
                            gr_item_element.setAttribute(export_shape_attrs[4],
                                                         export_str)

                        # The current shape can just be an attribute.
                        elif attr == export_shape_attrs[5]:
                            gr_item_element.setAttribute(export_shape_attrs[5],
                                                         gr_item.curr_shape)

                        # Get all of the coordinates of the current polygon. It will
                        # contain all of custom buttons, but rectangles will have a
                        # place holder shape to keep file size down.
                        elif attr == export_shape_attrs[6]:
                            points_element = xml_doc.createElement(export_shape_attrs[6])
                            gr_item_element.appendChild(points_element)
                            item_coords = gr_item.curr_coords
                            counter = 1
                            for coord in item_coords:
                                coord_element = xml_doc.createElement("p%s" % counter)
                                points_element.appendChild(coord_element)
                                coord_element.setAttribute("x", format(coord[0], ".3f"))
                                coord_element.setAttribute("y", format(coord[1], ".3f"))
                                counter += 1

                    shape_counter += 1

                else:
                    continue


        # Now write the file to disk.
        xml_str = xml_doc.toprettyxml(indent="    ")
        with open(filename, "w") as fh:
            fh.write(xml_str)

        print("Saved to: %s" % filename)
        return filename

    def load_xml_file(self):
        """
        Opens a dialog to find an xml file, then loads the tabs and graphics items.

        :return: The file loaded.
        :type: str
        """
        # Prompt the user starting at their home directory.
        filename, ffilter = QtWidgets.QFileDialog.getOpenFileName(caption="Load File",
                                                            dir=PickerToolEnums.USER_DOCS,
                                                            filter="XML files (*.xml)")

        # If we didn't get a filename, then do nothing.
        if not filename:
            return None
        if not os.path.exists(filename):
            print("File does not exist: %s" % filename)

        # Read in the XML and get the root.
        xml_fh = et.parse(filename)
        root = xml_fh.getroot()

        export_btn_attrs = PickerToolEnums.EXPORT_BTN_ATTRS
        export_img_attrs = PickerToolEnums.EXPORT_IMG_ATTRS

        # Find the children of the root node.
        tabs = root.getchildren()

        for tab in tabs:

            # Create the tab and make its GraphicsScene too.
            tab_name = tab.tag
            new_tab_index = self.create_tab(tab_name=tab_name)
            new_gr_scene = self.tabs_dict[new_tab_index]

            categories = tab.getchildren()

            for category in categories:

                # There can only be two categories: "SHAPES" and "IMAGES".
                if category.tag == PickerToolEnums.XML_BTN_CATEGORY:

                    shapes = category.getchildren()

                    for shape in shapes:
                        attrs = shape.getchildren()

                        # Extract the sel_objs and curr_shape. If it's an empty string 
                        # make it an empty list.
                        shape_sel_filter = filter(None,
                            shape.attrib[export_btn_attrs[4]].split(", "))
                        shape_sel_objs = list(shape_sel_filter)
                        
                        # Extract the current shape.
                        curr_shape_attr = export_btn_attrs[5]
                        set_shape = shape.attrib[curr_shape_attr]
                        
                        # We want to create kwargs to send to the 
                        new_pos = QtCore.QPointF(0.0, 0.0)
                        send_kwargs = {}

                        for attr in attrs:

                            # Extract the brush color and make it into a usable QColor.
                            if attr.tag == export_btn_attrs[0]:
                                new_brush = QtGui.QBrush(
                                    QtGui.QColor(int(attr.attrib["R"]),
                                                 int(attr.attrib["G"]),
                                                 int(attr.attrib["B"]),
                                                 255))
                                send_kwargs[export_btn_attrs[0]] = new_brush

                            # Extract the text. Later on the text may be more complex.
                            elif attr.tag == export_btn_attrs[1]:
                                new_text = str(attr.attrib["text"])
                                send_kwargs[export_btn_attrs[1]] = new_text

                            # Extract the bounding rect at the origin. Set the
                            # pos after creating the button.
                            elif attr.tag == export_btn_attrs[3]:
                                rect_dimensions = [int(attr.attrib["width"]),
                                                   int(attr.attrib["height"])]
                                new_rect = QtCore.QRect(0, 0,
                                                        rect_dimensions[0],
                                                        rect_dimensions[1])
                                send_kwargs[export_btn_attrs[3]] = new_rect

                            # Get the points for the polygon.
                            elif attr.tag == export_btn_attrs[6]:
                                points_list = attr.getchildren()
                                send_coord_list = []
                                for point in points_list:
                                    new_list = [float(point.attrib["x"]),
                                                 float(point.attrib["y"])]
                                    send_coord_list.append(new_list)

                                send_kwargs[export_btn_attrs[6]] = send_coord_list

                            # Extract the position and z value.
                            elif attr.tag == export_btn_attrs[2]:
                                new_pos.setX(float(attr.attrib["x"]))
                                new_pos.setY(float(attr.attrib["y"]))
                                z_val = float(attr.attrib["z"])

                        # Now we have the kwargs and data to make the graphics button.
                        send_kwargs[curr_shape_attr] = set_shape
                        new_polygon = GraphicsButton(main=True, sel_list=shape_sel_objs,
                                                     **send_kwargs)
                        new_polygon.update_polygon()
                        new_gr_scene.addItem(new_polygon)
                        new_polygon.setPos(new_pos)
                        new_polygon.setZValue(z_val)

                        # Make sure the new tab corresponds with the edit mode.
                        if self.edit_mode is True:
                            edit_flags = QtWidgets.QGraphicsItem.ItemIsSelectable | \
                                         QtWidgets.QGraphicsItem.ItemIsMovable
                        else:
                            edit_flags = QtWidgets.QGraphicsItem.ItemIsSelectable
                        new_polygon.setFlags(edit_flags)

                elif category.tag == PickerToolEnums.XML_IMG_CATEGORY:

                    # Loop through the images and create pixmap items for them.
                    images = category.getchildren()

                    for image in images:

                        attrs = image.getchildren()

                        # extract the file path and make a default position at the center.
                        filpath_attr = export_img_attrs[1]
                        img_file_path = image.attrib[filpath_attr]
                        good_img = True
                        new_pos = QtCore.QPointF(0.0, 0.0)
                        z_val = -1.0

                        for attr in attrs:

                            if attr.tag == export_img_attrs[0]:
                                new_pos.setX(float(attr.attrib["x"]))
                                new_pos.setY(float(attr.attrib["y"]))
                                z_val = float(attr.attrib["z"])

                        # Check if the file path exists for the image, if it doesn't then
                        # use the lost_image.png in the config file.
                        if not os.path.exists(img_file_path):
                            img_file_path = os.path.join(PickerToolEnums.WORKING_DIR,
                                                         PickerToolEnums.CONFIG_FOLDER,
                                                         PickerToolEnums.LOST_IMAGE)
                            good_img = False

                        # Now we have the kwargs to make the graphics button.
                        new_pixmap = GraphicsPixmap(image=img_file_path,
                                                    good_img=good_img)
                        new_gr_scene.addItem(new_pixmap)
                        new_pixmap.setPos(new_pos)
                        new_pixmap.setZValue(z_val)

        print("Loaded file: %s" % filename)
        return filename

    def exit_window(self):
        """
        Closes the Picker Tool
        """
        self.close()

    def create_edit_menu(self, menu_bar=None):
        """
        Creates the edit menu on the menu bar.

        :param menu_bar: The main menu bar we're adding to.
        :type: QtWidgets.QMenuBar
        """
        if not menu_bar:
            return None

        # Edit menu.
        edit_menu = menu_bar.addMenu("Edit")

        # Toggle Editing the tabs.
        tgl_edit = QtWidgets.QAction("Toggle Editing", self)
        tgl_edit_icon = QtGui.QIcon(PickerIcons.TOGGLE_EDIT_ICON)
        tgl_edit.setIcon(tgl_edit_icon)
        tgl_edit.triggered.connect(self.toggle_edit_mode)
        edit_menu.addAction(tgl_edit)

        # Show the settings layout.
        show_settings = QtWidgets.QAction("Show Settings", self)
        show_settings_icon = QtGui.QIcon(PickerIcons.SHOW_SET_ICON)
        show_settings.setIcon(show_settings_icon)
        show_settings.triggered.connect(self.show_settings)
        edit_menu.addAction(show_settings)

        # Hide the settings layout.
        hide_settings = QtWidgets.QAction("Hide Settings", self)
        hide_settings_icon = QtGui.QIcon(PickerIcons.HIDE_SET_ICON)
        hide_settings.setIcon(hide_settings_icon)
        hide_settings.triggered.connect(self.hide_settings)
        edit_menu.addAction(hide_settings)

    def toggle_edit_mode(self):
        """
        Toggles editing for the entire GUI.
        """
        # Flip the edit mode.
        if self.edit_mode is True:
            self.edit_mode = False
        else:
            self.edit_mode = True

        self.set_edit_mode()

    def set_edit_mode(self):
        """
        Sets editing for the entire GUI based on the self.edit_mode flag.
        """
        # The edit_widget flag use widget.setDisabled(), so their flag is reversed.
        if self.edit_mode is True:
            edit_flags = QtWidgets.QGraphicsItem.ItemIsSelectable | \
                         QtWidgets.QGraphicsItem.ItemIsMovable
            edit_widget = False
        else:
            edit_flags = QtWidgets.QGraphicsItem.ItemIsSelectable
            edit_widget = True

        # Toggles the movability.
        gr_scenes = self.tabs_dict.values()
        for gr_scene in gr_scenes:
            all_items = gr_scene.items()
            for item in all_items:
                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    item.set_edit_mode(self.edit_mode)
                    continue
                item.setFlags(edit_flags)

        # Toggles the widgets.
        for grp_box in self.window_widgets:
            grp_box.setDisabled(edit_widget)

    def show_settings(self):
        """
        Hides all the editing settings.
        """
        for grp_box in self.window_widgets:
            grp_box.setVisible(True)

    def hide_settings(self):
        """
        Hides all the editing settings.
        """
        for grp_box in self.window_widgets:
            grp_box.setVisible(False)

    def create_namespace_menu(self, menu_bar):
        """
        Creates the namespace menu on the menu bar.

        :param menu_bar: The main menu bar we're adding to.
        :type: QtWidgets.QMenuBar
        """
        if not menu_bar:
            return None

        # Namespace menu.
        self.namespace_menu = menu_bar.addMenu("Namespace")

        # Refresh list of namespaces.
        self.refresh_ns = QtWidgets.QAction("Refresh Namespaces", self)
        refresh_icon = QtGui.QIcon(PickerIcons.REFRESH_NS_ICON)
        self.refresh_ns.setIcon(refresh_icon)
        self.refresh_ns.triggered.connect(self.refresh_namespace)
        self.namespace_menu.addAction(self.refresh_ns)

        self.namespace_menu.addSeparator()

        # None option.
        self.none_ns = QtWidgets.QAction("None", self)
        self.none_ns.setObjectName("None")
        self.none_ns.setCheckable(True)
        self.none_ns.setChecked(True)
        self.none_ns.triggered.connect(self.set_namespace)
        self.namespace_menu.addAction(self.none_ns)

    def refresh_namespace(self):
        """
        Refreshes the namespace list by gathering all the namespaces of the scene. And
        populate the context menu.

        :param ns_menu: The namespace menu of the main picker tool window.
        :type: QtWidgets.QMenu
        """
        if not self.namespace_menu:
            return None

        # Clear the current namespace to an empty string, not None, and get namespaces.
        self.curr_ns = ""
        scene_namespaces = self.get_namespaces()
        self.set_namespace_view()

        # Clear the menu and re-add the refresh and none action.
        self.namespace_menu.clear()
        self.namespace_menu.addAction(self.refresh_ns)
        self.namespace_menu.addSeparator()
        self.namespace_menu.addAction(self.none_ns)
        self.none_ns.setChecked(True)

        for namespace in scene_namespaces:

            # Create a QAction using the namespace's name.
            ns_act = QtWidgets.QAction(namespace, self)
            ns_act.setCheckable(True)
            ns_act.setObjectName(namespace)
            ns_act.triggered.connect(self.set_namespace)
            self.namespace_menu.addAction(ns_act)

    def set_namespace(self):
        """
        Sets the namespace for the Maya scene.
        """
        sender = self.sender()
        if sender:

            # Uncheck all the current actions.
            ns_acts = self.namespace_menu.actions()
            for act in ns_acts:
                if act.isCheckable():
                    act.setChecked(False)

            # Set the toggled action to checked.
            sender.setChecked(True)

            # If the user chose "None" then the current namespace is empty, not None
            if sender.objectName() == "None":
                self.curr_ns = ""
            else:
                self.curr_ns = sender.objectName()
            self.set_namespace_view()

    def set_namespace_view(self):
        """
        Sets the namespace for all of the graphics views.
        :return:
        """
        if not self.curr_ns:
            send_ns = ""
        else:
            send_ns = self.curr_ns

        # Get the tab's graphics views and set the namespace.
        tab_count = self.tab_widget.count()
        for count in range(tab_count):
            curr_gr_view = self.tab_widget.widget(count)
            curr_gr_view.namespace = send_ns

    def get_namespaces(self):
        """
        Gathers the namespaces of the current Maya scene.

        :return: list of namespaces in the scene.
        :type: list
        """
        # Get all the references of the scene.
        ref_nodes = cmds.ls(type="reference")

        send_list = []
        for ref_node in ref_nodes:
            got_ns = cmds.referenceQuery(ref_node, namespace=True)[1:]
            send_list.append(got_ns)

        return send_list

    def tab_changed(self, index):
        """
        When the tabs change, it will set the current working scene.
        """
        # Ensure there are any tabs.
        tab_count = self.tab_widget.count()
        if tab_count < 1:
            return None

        # Clear the selection of the previous scene first. And un-highlight all buttons.
        self.curr_scene.clearSelection()
        for item in self.curr_scene.items():
            item.highlight_button(False)

        # Now we can get a new scene from the tabs_dict and set it.
        try:
            set_scene = self.tabs_dict[index]
        except KeyError:
            set_scene = None
        self.curr_scene = set_scene

    def create_settings_layout(self):
        """
        Creates the settings tab.

        :return: The main layout holding all the group boxes.
        :type: QtWidgets.QVBoxLayout
        """
        main_vb = QtWidgets.QVBoxLayout()

        # Creates the main ui grp box.
        main_ui_layout = self.create_main_ui_grp_box()
        main_vb.addWidget(main_ui_layout)
        self.window_widgets.append(main_ui_layout)

        # Creates the picker grp box.
        picker_grp_box = self.create_picker_grp_box()
        main_vb.addWidget(picker_grp_box)
        self.window_widgets.append(picker_grp_box)

        # Set the main vb properties.
        main_vb.setContentsMargins(0, 0, 5, 0)
        main_vb.setSpacing(2)

        return main_vb

    def create_main_ui_grp_box(self):
        """
        Creates the main ui layout holding the buttons to edit the tabs.

        :return: A group box holding all the buttons.
        :type: QtWidgets.QGroupBox
        """
        # Creates the group box we're adding to.
        main_grp_box = QtWidgets.QGroupBox("Main UI")

        # HBox for the grp box.
        top_hb = QtWidgets.QHBoxLayout()

        # Buttons for the grp box.
        create_tab_btn = QtWidgets.QPushButton("Create Tab")
        create_tab_icon = QtGui.QIcon(PickerIcons.CREATE_TAB_ICON)
        create_tab_btn.setIcon(create_tab_icon)
        create_tab_btn.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                  QtWidgets.QSizePolicy.Maximum)
        create_tab_btn.clicked.connect(self.create_tab)
        top_hb.addWidget(create_tab_btn)

        rename_tab_btn = QtWidgets.QPushButton("Rename Tab")
        rename_tab_icon = QtGui.QIcon(PickerIcons.RENAME_TAB_ICON)
        rename_tab_btn.setIcon(rename_tab_icon)
        rename_tab_btn.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                     QtWidgets.QSizePolicy.Maximum)
        rename_tab_btn.clicked.connect(self.rename_tab)
        top_hb.addWidget(rename_tab_btn)

        remove_tab_btn = QtWidgets.QPushButton("Remove Tab")
        remove_tab_icon = QtGui.QIcon(PickerIcons.REMOVE_TAB_ICON)
        remove_tab_btn.setIcon(remove_tab_icon)
        remove_tab_btn.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                     QtWidgets.QSizePolicy.Maximum)
        remove_tab_btn.clicked.connect(self.remove_tab)
        top_hb.addWidget(remove_tab_btn)

        # Set the HBox's margin spaces.
        top_hb.setContentsMargins(0, 0, 0, 0)

        # Set the grp box's layout.
        main_grp_box.setLayout(top_hb)

        return main_grp_box

    def create_tab(self, tab_name=None):
        """
        Creates the tab.

        :param tab_name: Name of the new tab.
        :type: str

        :return: The index of the new tab.
        :type: int
        """
        if not tab_name:
            # Open a dialog to get the name of the tab if it wasn't given.
            text, ok = QtWidgets.QInputDialog().getText(self, "Tab Name",
                                                        "Enter the tab's name:")

            # If nothing is entered, then quit.
            if text == "":
                return None
            tab_name = text

        # Create the GraphicsScene and GraphicsView
        tab_scene = GraphicsScene(self)
        tab_scene.selectionChanged.connect(self.update_tree_view)
        tab_view = GraphicsView(gr_scene=tab_scene, main_wnd_ref=self)
        tab_index = self.tab_widget.addTab(tab_view, tab_name)

        # Ensure the tabs_dict has the new tab and set the new tab as the current one.
        self.tabs_dict[tab_index] = tab_scene
        self.curr_scene = tab_scene
        self.tab_widget.setCurrentIndex(tab_index)

        # Make sure the tab starts at the center.
        tab_view.centerOn(0.0, 0.0)

        # Make sure the new tab has the namespace set to the current one.
        tab_view.namespace = self.curr_ns

        return tab_index

    def rename_tab(self):
        """
        Opens a dialog for to rename the current tab.
        """
        # Asks the user what the name should be.
        text, ok = QtWidgets.QInputDialog().getText(self, "New name",
                                                    "Enter the tab's new name:")

        # If nothing is entered, then quit.
        if text == "":
            return None

        # Get the current tab and set the text.
        tab_index = self.tab_widget.currentIndex()
        self.tab_widget.setTabText(tab_index, text)

    def remove_tab(self):
        """
        Removes the current tab and fix the tabs_dict.
        """
        # Ensure we have a tab to work with.
        curr_tab_index = self.tab_widget.currentIndex()
        if curr_tab_index is None:
            return None

        self.tab_widget.removeTab(curr_tab_index)
        self.tabs_dict.pop(curr_tab_index, None)

        # Fix the tabs_dict by recreating the tabs dictionary to align the tab index with
        # it's graphics scene.
        self.tabs_dict.clear()
        for tab_count in range(self.tab_widget.count()):
            self.tabs_dict[tab_count] = self.tab_widget.widget(tab_count).scene()

        # Now with a good tabs_dict, we can set the current scene.
        new_curr_tab_index = self.tab_widget.currentIndex()
        if new_curr_tab_index == -1:
            self.curr_scene = None
        else:
            self.curr_scene = self.tabs_dict[new_curr_tab_index]

    def create_picker_grp_box(self):
        """
        Creates the picker group box for creating buttons.

        :return: A group box holding the options to make buttons.
        :type: QtWidgets.QGroupBox
        """
        # Creates the group box we're adding to.
        main_grp_box = QtWidgets.QGroupBox("Picker")

        # VBox for the grp box we're adding to.
        main_vb = QtWidgets.QVBoxLayout()

        # Upper and lower horizontal box.
        upper_hb = QtWidgets.QHBoxLayout()
        lower_hb = QtWidgets.QHBoxLayout()

        # Make horizontal lines and vertical lines.
        h_line_creator = HLine()
        v_line_creator = VLine()

        # Create the picker visual settings - add to the upper hb.
        picker_settings_layout = self.create_picker_settings()
        upper_hb.addLayout(picker_settings_layout)

        # Add a vertical line between.
        v_line_1 = v_line_creator.make_line()
        upper_hb.addWidget(v_line_1)

        # Create the scene edit settings - add to the upper hb.
        scene_edit_layout = self.create_scene_edit_layout()
        upper_hb.addLayout(scene_edit_layout)

        # Create the picker display and scene edit options - add to the lower hb.
        display_picker_layout = self.create_picker_display()
        lower_hb.addLayout(display_picker_layout)

        # Add a vertical line between.
        v_line_2 = v_line_creator.make_line()
        lower_hb.addWidget(v_line_2)

        # Create the selected objects list - add to the lower hb.
        sel_obj_layout = self.create_selected_objs_layout()
        lower_hb.addLayout(sel_obj_layout)

        # Set the box layout's properties.
        upper_hb.setContentsMargins(0, 0, 0, 0)
        lower_hb.setContentsMargins(0, 0, 0, 0)
        main_vb.setContentsMargins(0, 0, 0, 0)

        # Put the upper and lower in the main vb, with a horizontal line between,
        # and set the main vb to the main grp box.
        main_vb.addLayout(upper_hb)
        h_line_1 = h_line_creator.make_line()
        main_vb.addWidget(h_line_1)
        main_vb.addLayout(lower_hb)
        main_grp_box.setLayout(main_vb)

        return main_grp_box

    def create_picker_settings(self):
        """
        Creates the picker visual settings layout.

        :return: A layout holding the visual settings options.
        :type: QtWidgets.FormLayout
        """
        main_form = QtWidgets.QFormLayout()

        # Picker Label line edit, this will be the text on the picker button.
        self.picker_label_le = QtWidgets.QLineEdit()
        self.picker_label_le.textChanged["QString"].connect(self.update_text)
        main_form.addRow("Label:", self.picker_label_le)

        # Picker shape, can be custom.
        picker_shape_cb = QtWidgets.QComboBox()
        picker_shape_cb.addItems(PickerToolEnums.SHAPES)
        picker_shape_cb.setCurrentIndex(0)
        picker_shape_cb.currentTextChanged["QString"].connect(self.update_shape)
        main_form.addRow("Shape:", picker_shape_cb)

        # Custom picker shape settings. Start off disabled.
        picker_shape_hb = QtWidgets.QHBoxLayout()
        self.prec_cb = QtWidgets.QComboBox()
        self.prec_cb.addItems(PickerToolEnums.PRECISIONS)
        self.prec_cb.setCurrentIndex(0)
        self.shape_precision = PickerToolEnums.PRECISIONS_DICT[self.prec_cb.currentText()]
        self.prec_cb.currentTextChanged["QString"].connect(self.update_precision)
        self.prec_cb.setDisabled(True)
        self.get_shape_btn = QtWidgets.QPushButton("Get")
        self.get_shape_btn.clicked.connect(self.get_shape_from_scene)
        self.get_shape_btn.setDisabled(True)
        picker_shape_hb.addWidget(self.prec_cb)
        picker_shape_hb.addWidget(self.get_shape_btn)
        main_form.addRow("Precision", picker_shape_hb)

        # Picker Width line edit, this will be the width of the picker button.
        self.picker_width_slid = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.picker_width_slid.setRange(25, 100)
        self.picker_width_slid.valueChanged.connect(self.update_width_spbx)
        # Picker corresponding width line edit. Add the slider and line edit together.
        self.picker_width_spbx = QtWidgets.QSpinBox()
        self.picker_width_spbx.setRange(25, 200)
        self.picker_width_spbx.setFixedWidth(50)
        self.picker_width_spbx.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.picker_width_spbx.valueChanged.connect(self.update_width)
        picker_width_hb = QtWidgets.QHBoxLayout()
        picker_width_hb.addWidget(self.picker_width_slid)
        picker_width_hb.addWidget(self.picker_width_spbx)
        main_form.addRow("Width:", picker_width_hb)

        # Picker Height line edit, this will be the height of the picker button.
        self.picker_height_slid = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.picker_height_slid.setRange(25, 100)
        self.picker_height_slid.valueChanged.connect(self.update_height_spbx)
        # Picker corresponding height line edit. Add the slider and line edit together.
        self.picker_height_spbx = QtWidgets.QSpinBox()
        self.picker_height_spbx.setRange(25, 200)
        self.picker_height_spbx.setFixedWidth(50)
        self.picker_height_spbx.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.picker_height_spbx.valueChanged.connect(self.update_height)
        picker_height_hb = QtWidgets.QHBoxLayout()
        picker_height_hb.addWidget(self.picker_height_slid)
        picker_height_hb.addWidget(self.picker_height_spbx)
        main_form.addRow("Height:", picker_height_hb)

        # Picker color, this will be the default color of the picker button.
        self.picker_color_btn = QtWidgets.QPushButton()
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(155, 0, 155))
        self.picker_color_btn.setPalette(palette)
        self.picker_color_btn.clicked.connect(self.change_color_clicked)
        main_form.addRow("Color:", self.picker_color_btn)

        return main_form

    def update_text(self, text):
        """
        Updates the text on the preview shape.

        :param text: New string to show.
        :type: str
        """
        self.pp_item.update_text(text)

    def update_shape(self, new_text):
        """
        Update the shape in the picker preview based on the text in the shape combo box.
        """
        if not new_text:
            return None

        if new_text == PickerToolEnums.SHAPES[2]:
            self.prec_cb.setDisabled(False)
            self.get_shape_btn.setDisabled(False)
            self.pp_item.update_curr_shape(new_text)
        else:
            self.prec_cb.setDisabled(True)
            self.get_shape_btn.setDisabled(True)
            self.pp_item.update_curr_shape(new_text)

    def update_precision(self, prec_text):
        """
        Updates the precision for the custom shape.
        """
        if not prec_text:
            return None

        self.shape_precision = PickerToolEnums.PRECISIONS_DICT[prec_text]

    def get_shape_from_scene(self):
        """
        Get the coordinates of the CC from the scene.
        """
        # Get and verify the contents of the selected items, and use the only item in the
        # returned list if we got a valid selection.
        # NOTE: This will only take a single nurbsCurve, so it will check for multiple
        # nurbsCurves selected. Even if many other types are selected, we will extract
        # the nurbsCurves out of the selection.
        curr_sel = get_selected_items(multi=False, type=["nurbsCurve"])
        if not curr_sel:
            return None
        else:
            curr_sel = curr_sel[0]

        # Get 100 points along the curve using cmds.pointOnCurve
        creation_points = []
        counter = 0.0
        while counter <= 1.0:
            coordinates = cmds.pointOnCurve(curr_sel, parameter=counter,
                                            position=True, turnOnPercentage=True)
            x_coord = format(coordinates[0], ".3f")     # X coord in Maya
            y_coord = format(coordinates[2], ".3f")     # Z coord in Maya scene.
            creation_points.append([x_coord, y_coord])
            counter += self.shape_precision

        # Find the minimum x and y, and maximum x and y.
        x_min, x_max = None, None
        y_min, y_max = None, None
        for point in creation_points:
            x = float(point[0])
            y = float(point[1])

            if x_min is None and x_max is None:
                x_min = x
                x_max = x
            if y_min is None and y_max is None:
                y_min = y
                y_max = y

            if x < x_min:
                x_min = x
            elif x > x_max:
                x_max = x

            if y < y_min:
                y_min = y
            elif y > y_max:
                y_max = y

        x_length = x_max - x_min
        y_length = y_max - y_min

        # Determine the square's dimensions based on which axis is taller.
        square_length = x_length if x_length > y_length else y_length
        scale_factor = PickerToolEnums.MINIMUM_SIZE / square_length

        # Convert all of the coordinates to the 0-25 scale.
        new_creation_points = []
        for point in creation_points:
            normalized_x = float(point[0]) - x_min
            x_new = (normalized_x * scale_factor)

            normalized_y = float(point[1]) - y_min
            y_new = (normalized_y * scale_factor)

            new_creation_points.append([x_new, y_new])

        self.pp_item.update_polygon(new_creation_points)

    def update_width_spbx(self, value):
        """
        Updates the spin box after the slider is changed.
        """
        self.picker_width_spbx.setValue(value)

    def update_width(self, value):
        """
        Updates the width line edit and the rectangle's width.

        :param value: The current value of the slider.
        :type: int
        """
        if not value:
            return None

        # Set the width line edit.
        self.picker_width_slid.setValue(value)

        # Set the width of the preview rect's width. Get the old height and reuse that.
        old_rect = self.pp_item.set_rect
        self.pp_item.update_bounding_rect(QtCore.QRect(old_rect.x(), old_rect.y(),
                                                        float(value), old_rect.height()))

        # Center the picker preview
        item_center = self.get_center(self.pp_item)
        self.pick_prvw_view.centerOn(item_center)

    def update_height_spbx(self, value):
        """
        Updates the spin box after the slider is changed.
        """
        self.picker_height_spbx.setValue(value)

    def update_height(self, value):
        """
        Updates the height line edit and the rectangle's height.

        :param value: The current value of the slider.
        :type: int
        """
        if not value:
            return None

        # Set the width line edit.
        self.picker_height_slid.setValue(value)

        # Set the width of the preview rect's width. Get the old height and reuse that.
        old_rect = self.pp_item.set_rect
        self.pp_item.update_bounding_rect(QtCore.QRect(old_rect.x(), old_rect.y(),
                                                        old_rect.width(), float(value)))

        # Center the picker preview.
        item_center = self.get_center(self.pp_item)
        self.pick_prvw_view.centerOn(item_center)

    def change_color_clicked(self):
        """
        Open the QColorDialog, and pick a color to set all the selected CCs.

        :return: RGB values in 0-255, 0-255, 0-255
        :type: tuple
        """
        # Display the QColorDialog.
        colors_QColor = QtWidgets.QColorDialog().getColor()
        if colors_QColor.isValid():

            # Get a float value, for Maya, and an rgb value, for the GUI.
            colors_rgb = colors_QColor.getRgb()

            # Change the color of the button to the new color.
            palette = QtGui.QPalette()
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(colors_rgb[0],
                                                                 colors_rgb[1],
                                                                 colors_rgb[2]))
            self.picker_color_btn.setPalette(palette)

            # Change the color of the class's preview rect.
            new_brush = QtGui.QBrush(QtGui.QColor(colors_rgb[0], colors_rgb[1],
                                                  colors_rgb[2], 255))
            self.pp_item.update_brush_color(new_brush)

    def create_scene_edit_layout(self):
        """
        Creates the options to edit elements in the graphics scene.

        :return: A layout containing options to edit elements in the graphics scene.
        :type: QtWidgets.QVBoxLayout
        """
        main_form = QtWidgets.QFormLayout()

        # Create the search and replace settings.
        snr_layout = self.create_search_replace_layout()
        main_form.addRow(snr_layout)

        # Create the set reference buttons.
        set_ref_layout = self.create_ref_button_layout()
        main_form.addRow(set_ref_layout)

        # Create the z settings layout.
        set_z_layout = self.create_z_layout()
        main_form.addRow(set_z_layout)

        # Create the align buttons.
        align_layout = self.create_scene_align_layout()
        main_form.addRow(align_layout)

        # Create the mirror buttons.
        mirror_layout = self.create_mirror_layout()
        main_form.addRow(mirror_layout)

        return main_form
    
    def create_search_replace_layout(self):
        """
        Creates the search and replace form layout, combined with its apply button.

        :return: A layout holding the search and replace layout with an apply button.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        # Creates the form layout first.
        form_layout = QtWidgets.QFormLayout()
        self.scene_search_le = QtWidgets.QLineEdit()
        form_layout.addRow("Search:", self.scene_search_le)
        self.scene_replace_le = QtWidgets.QLineEdit()
        form_layout.addRow("Replace:", self.scene_replace_le)
        main_hb.addLayout(form_layout)

        # Creates the apply button.
        apply_text_chg_btn = QtWidgets.QPushButton("Apply")
        apply_text_chg_btn.clicked.connect(self.search_and_replace_text)
        main_hb.addWidget(apply_text_chg_btn)

        return main_hb

    def search_and_replace_text(self):
        """
        Searches the selected items and checks for their text to replace it. This will
        replace all instances of the search string. Meaning if an item had "l_roll_l_up"
        and we wanted to replace "l_" to "r_", it will update it to "r_roll_r_up"
        """
        sel_items = self.curr_scene.selectedItems()
        search_str = self.scene_search_le.text()
        replace_str = self.scene_replace_le.text()

        # Search through for any item with the search string, copy the text into a new
        # variable, then replace the search string with the new one and update.
        for item in sel_items:
            if search_str in item.text:
                orig_text = copy.deepcopy(item.text)
                new_text = orig_text.replace(search_str, replace_str)
                item.update_text(new_text)
    
    def create_ref_button_layout(self):
        """
        Creates the reference button layout. These are the buttons for setting a
        reference point for the buttons to mirror and align from.

        :return: A layout holding the buttons for setting a reference button.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        # Create the Set Ref button.
        set_ref_btn = QtWidgets.QPushButton("Set Ref")
        set_ref_icon = QtGui.QIcon(PickerIcons.SET_REF_ICON)
        set_ref_btn.setIcon(set_ref_icon)
        set_ref_btn.clicked.connect(self.set_ref_item)
        main_hb.addWidget(set_ref_btn)

        # Create the Clear Ref button. Start this button disabled. It's only available
        # after a reference button is set.
        self.clear_ref_btn = QtWidgets.QPushButton("Clear")
        self.clear_ref_btn.setFixedWidth(50)
        self.clear_ref_btn.clicked.connect(self.clear_ref_item)
        self.clear_ref_btn.setDisabled(True)
        main_hb.addWidget(self.clear_ref_btn)

        return main_hb

    def set_ref_item(self, item=None):
        """
        Sets the reference button for the current tab.

        :param item: The item we're setting as the reference.
        :type: list
        """
        # Usually just takes whatever is selected, unless it was passed in.
        if item:
            sel_items = item
        else:
            sel_items = self.curr_scene.selectedItems()
            if not sel_items:
                return None

        # Will only use the first element as the ref item.
        self.curr_scene.ref_item = sel_items[0]

        # Make sure to open up the clear button.
        self.clear_ref_btn.setDisabled(False)

    def clear_ref_item(self):
        """
        Sets the reference button to None.
        """
        self.curr_scene.ref_item = None
        self.clear_ref_btn.setDisabled(True)
    
    def create_z_layout(self):
        """
        Creates the z buttons layout. These are the buttons for moving graphics buttons
        forward or back.

        :return: A layout holding the buttons for setting z buttons.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        # Create the Bring Forward button.
        bring_forward_btn = QtWidgets.QPushButton("Forward")
        fwd_icon = QtGui.QIcon(PickerIcons.MOVE_UP)
        bring_forward_btn.setIcon(fwd_icon)
        bring_forward_btn.clicked.connect(self.bring_forward)
        main_hb.addWidget(bring_forward_btn)

        # Create the Send Back button.
        send_back_btn = QtWidgets.QPushButton("Back")
        back_icon = QtGui.QIcon(PickerIcons.MOVE_DOWN)
        send_back_btn.setIcon(back_icon)
        send_back_btn.clicked.connect(self.send_backward)
        main_hb.addWidget(send_back_btn)

        return main_hb

    def bring_forward(self):
        """
        Brings the graphics button forward.
        """
        sel_items = self.curr_scene.selectedItems()
        if not sel_items:
            return None

        for item in sel_items:
            curr_z_value = item.zValue()
            item.setZValue(curr_z_value + 0.01)

    def send_backward(self):
        """
        Brings the graphics button forward.
        """
        sel_items = self.curr_scene.selectedItems()
        if not sel_items:
            return None

        for item in sel_items:
            curr_z_value = item.zValue()
            item.setZValue(curr_z_value - 0.01)
    
    def create_scene_align_layout(self):
        """
        Creates the align buttons layout.

        :return: A layout holding the buttons for aligning scene elements.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        # Create the Align X button.
        align_x_btn = QtWidgets.QPushButton("Align X")
        align_x_icon = QtGui.QIcon(PickerIcons.ALIGN_X_ICON)
        align_x_btn.setIcon(align_x_icon)
        align_x_btn.clicked.connect(self.align_by_x)
        main_hb.addWidget(align_x_btn)

        # Create the Align Y button.
        align_y_btn = QtWidgets.QPushButton("Align Y")
        align_y_icon = QtGui.QIcon(PickerIcons.ALIGN_Y_ICON)
        align_y_btn.setIcon(align_y_icon)
        align_y_btn.clicked.connect(self.align_by_y)
        main_hb.addWidget(align_y_btn)

        return main_hb

    def align_by_x(self):
        """
        Align the selected buttons by their Xs. If a ref item exists, then align the
        items by that. If not, then average the X positions and use that.
        """
        ref_item = self.curr_scene.ref_item

        # If there is a ref item, get its X position, and set all the items to that.
        if ref_item:

            # Get the X center of the ref_item.
            ref_item_center = self.get_center(ref_item)
            ref_item_x = ref_item_center.x()
            sel_items = self.curr_scene.selectedItems()
            for item in sel_items:
                # Use the center of the ref_item, don't need the Y, and convert it to the
                # item's new top left coordinate.
                x_new_center = self.convert_from_center(QtCore.QPointF(ref_item_x, 0),
                                                        item)
                item.setX(x_new_center.x())

        # Average all X positions of the selected items, then set them to that average.
        else:
            sel_items = self.curr_scene.selectedItems()
            # Add up all of the values of the centers of the items.
            x_total = 0.0
            for item in sel_items:
                x_total += self.get_center(item).x()

            x_average = x_total / len(sel_items)

            for item in sel_items:
                # Use the average, don't need the Y, and convert it to the
                # item's new top left coordinate.
                x_new_center = self.convert_from_center(QtCore.QPointF(x_average, 0),
                                                        item)
                item.setX(x_new_center.x())

    def align_by_y(self):
        """
        Align the selected buttons by their Ys. If a ref item exists, then align the
        items by that. If not, then average the Y positions and use that.
        """
        ref_item = self.curr_scene.ref_item

        # If there is a ref item, get its X position, and set all the items to that.
        if ref_item:

            # Get the Y center of the ref_item.
            ref_item_center = self.get_center(ref_item)
            ref_item_y = ref_item_center.y()
            sel_items = self.curr_scene.selectedItems()
            for item in sel_items:
                # Use the center of the ref_item, don't need the X, and convert it to the
                # item's new top left coordinate.
                y_new_center = self.convert_from_center(QtCore.QPointF(0, ref_item_y),
                                                        item)
                item.setY(y_new_center.y())

        # Average all Y positions of the selected items, then set them to that average.
        else:
            sel_items = self.curr_scene.selectedItems()
            # Add up all of the values of the centers of the items.
            y_total = 0.0
            for item in sel_items:
                y_total += self.get_center(item).y()

            y_average = y_total / len(sel_items)

            for item in sel_items:
                # Use the average, don't need the X, and convert it to the
                # item's new top left coordinate.
                y_new_center = self.convert_from_center(QtCore.QPointF(0, y_average),
                                                        item)
                item.setY(y_new_center.y())
    
    def create_mirror_layout(self):
        """
        Creates the mirror button layout.

        :return: A layout holding the buttons for setting a reference button.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        # Create the Mirror button.
        mirror_btn = QtWidgets.QPushButton("Mirror")
        mirror_icon = QtGui.QIcon(PickerIcons.MIRROR_ICON)
        mirror_btn.setIcon(mirror_icon)
        mirror_btn.clicked.connect(self.mirror_sel_btns)
        main_hb.addWidget(mirror_btn)

        # Mirror settings button to open the mirror dialog.
        mirror_setting_btn = QtWidgets.QPushButton()
        mirror_settings_icon = QtGui.QIcon(PickerIcons.MIRROR_SET_ICON)
        mirror_setting_btn.setIcon(mirror_settings_icon)
        mirror_setting_btn.setFixedWidth(40)
        mirror_setting_btn.clicked.connect(self.mirror_settings.init_gui)
        main_hb.addWidget(mirror_setting_btn)

        return main_hb

    def mirror_sel_btns(self):
        """
        Mirrors the selected buttons based on the mirror settings.
        """
        # Make sure we have selected items to work with.
        sel_items = self.curr_scene.selectedItems()
        if not sel_items:
            return None

        # Gather the info from the mirror dialog settings.
        mirror_x = self.mirror_settings.x_rdbtn.isChecked()
        mirror_y = self.mirror_settings.y_rdbtn.isChecked()
        mirror_on = self.mirror_settings.mirror_on_combo.currentText()
        mirror_type = self.mirror_settings.type_combo.currentText()

        # If no axis is given, don't mirror and let the user know.
        if not mirror_x and not mirror_y:
            print("Unable to mirror since no mirror axis set. Check the Mirror "
                  "Settings to set one.")
            return None

        # If the mirror settings are set to ref shape, but none have been set, then use
        # the world axis.
        if mirror_on == PickerToolEnums.MIRROR_ONS[1] and not self.curr_scene.ref_item:
            mirror_on = PickerToolEnums.MIRROR_ONS[0]

        if mirror_on == PickerToolEnums.MIRROR_ONS[1]:
            ref_item_center = self.get_center(self.curr_scene.ref_item)

        for item in sel_items:

            curr_item_center = self.get_center(item)
            new_rect = copy.deepcopy(item.set_rect)
            new_coords = copy.deepcopy(item.curr_coords)

            x_center_new = curr_item_center.x()
            y_center_new = curr_item_center.y()

            # If it's based on the ref shape, then we have to calculate the change.
            if mirror_on == PickerToolEnums.MIRROR_ONS[1]:

                # If we're mirroring on X, calculate the difference
                if mirror_x:
                    x_diff = curr_item_center.x() - ref_item_center.x()
                    x_center_new = ref_item_center.x() - x_diff

                # If we're mirroring on Y, calculate the difference
                if mirror_y:
                    y_diff = curr_item_center.y() - ref_item_center.y()
                    y_center_new = ref_item_center.y() - y_diff

            # If it's based on the world, then just flip the X and Y if applicable.
            elif mirror_on == PickerToolEnums.MIRROR_ONS[0]:
                if mirror_x:
                    x_center_new = -(x_center_new)
                if mirror_y:
                    y_center_new = -(y_center_new)

            # Convert the centers into the shape's top left corner, what PySide2 can use.
            new_shape_coord = self.convert_from_center(
                                            QtCore.QPointF(x_center_new, y_center_new),
                                            item)

            # Mirror the coordinates of the polygon too.
            if mirror_x:
                # Mirror the xs of the new_coords
                for coord in new_coords:
                    x_curr = coord[0]
                    x_diff = PickerToolEnums.MINIMUM_SIZE - x_curr
                    coord[0] = x_diff

            if mirror_y:
                # Mirror the ys of the new_coords
                for coord in new_coords:
                    y_curr = coord[1]
                    y_diff = PickerToolEnums.MINIMUM_SIZE - y_curr
                    coord[1] = y_diff

            # Now decide whether we create a new button or move the selected one.
            if mirror_type == PickerToolEnums.MIRROR_TYPES[0]:

                # Create a new item and set the new position after it is created.
                new_item_sel = copy.deepcopy(item.sel_objs)
                new_item_brush = QtGui.QBrush(QtGui.QColor(item.brush_col.color()))
                new_item_kwargs = {"set_rect": new_rect,
                                   "brush_col": new_item_brush,
                                   "text": copy.deepcopy(item.text),
                                   "curr_shape": copy.deepcopy(item.curr_shape),
                                   "curr_coords": new_coords}

                new_polygon = GraphicsButton(main=True, sel_list=new_item_sel,
                                             **new_item_kwargs)
                new_polygon.update_polygon()
                self.curr_scene.addItem(new_polygon)
                new_polygon.setPos(new_shape_coord)

            elif mirror_type == PickerToolEnums.MIRROR_TYPES[1]:
                item.setPos(new_shape_coord)
                item.update_bounding_rect(new_rect)
                item.update_polygon(new_coords)

        self.curr_scene.update()

    def create_picker_display(self):
        """
        Creates the picker display options and the graphics scene options.

        :return: A layout holding all the elements.
        :type: QtWidgets.QFormLayout
        """
        main_form = QtWidgets.QFormLayout()

        # Create the picker factory label and graphics view.
        picker_factory_label = QtWidgets.QLabel("Picker Preview")
        main_form.addRow(picker_factory_label)
        self.pick_prvw_scn = PickerPreviewGraphicsScene(self)
        self.pick_prvw_view = PickerPreviewGraphicsView(
                                                        gr_scene=self.pick_prvw_scn)
        self.pick_prvw_view.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                          QtWidgets.QSizePolicy.Fixed)
        main_form.addRow(self.pick_prvw_view)

        # Create the first shape in the preview. Get the color from the button's palette.
        btn_q_color = self.picker_color_btn.palette().color(QtGui.QPalette.Button)
        brush = QtGui.QBrush(btn_q_color)
        base_rect = QtCore.QRect(0, 0,
                                 self.picker_width_spbx.value(),
                                 self.picker_height_spbx.value())

        send_kwargs = {"set_rect": base_rect,
                       "brush_col": brush,
                       "text": ""}
        self.pp_item = GraphicsButton(main=False, **send_kwargs)
        self.pick_prvw_scn.addItem(self.pp_item)

        # Create the picker creation layout.
        picker_creation_layout = self.create_picker_creation_layout()
        main_form.addRow(picker_creation_layout)

        return main_form
    
    def create_picker_creation_layout(self):
        """
        Creates the picker creation layout. These are the buttons to create, delete,
        and update picker buttons. Also add a button to take a screenshot.

        :return: A layout with all the buttons for altering the scene.
        :type: QtWidgets.QVBoxLayout
        """
        main_vb = QtWidgets.QVBoxLayout()

        # Create the Create Button button.
        create_btn = QtWidgets.QPushButton("Create Button")
        create_btn_icon = QtGui.QIcon(PickerIcons.CREATE_BTN_ICON)
        create_btn.setIcon(create_btn_icon)
        create_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        create_btn.clicked.connect(self.create_btn)
        main_vb.addWidget(create_btn)

        # Create the Update Button button.
        update_btn = QtWidgets.QPushButton("Update Button")
        update_btn_icon = QtGui.QIcon(PickerIcons.UPDATE_BTN_ICON)
        update_btn.setIcon(update_btn_icon)
        update_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        update_btn.clicked.connect(self.update_btn)
        main_vb.addWidget(update_btn)

        # Create the Update Button's selection button.
        update_sel_btn = QtWidgets.QPushButton("Update Button Selection")
        update_sel_icon = QtGui.QIcon(PickerIcons.UPDATE_SEL_ICON)
        update_sel_btn.setIcon(update_sel_icon)
        update_sel_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        update_sel_btn.clicked.connect(self.update_btn_selection)
        main_vb.addWidget(update_sel_btn)

        # Create the Delete Picker button.
        delete_btn = QtWidgets.QPushButton("Delete Button")
        delete_btn_icon = QtGui.QIcon(PickerIcons.DEL_BTN_ICON)
        delete_btn.setIcon(delete_btn_icon)
        delete_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        delete_btn.clicked.connect(self.delete_btn)
        main_vb.addWidget(delete_btn)

        # Create the Front Screenshot button.
        scrn_shot_btn = QtWidgets.QPushButton("Take Screenshot")
        scrn_shot_btn_icon = QtGui.QIcon(PickerIcons.SCRN_SHOT_ICON)
        scrn_shot_btn.setIcon(scrn_shot_btn_icon)
        scrn_shot_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        scrn_shot_btn.clicked.connect(self.take_screenshot)
        main_vb.addWidget(scrn_shot_btn)

        return main_vb

    def create_btn(self, set_pos=None):
        """
        Copies the graphics button from the picker factory to the main window.

        :param set_pos: The new position of the button.
        :type: QtCore.QPointF
        """
        # Get and verify the selection from Maya.
        curr_sel = get_selected_items(multi=True)
        if not curr_sel:
            return None

        new_btn = GraphicsButton(main=True, sel_list=curr_sel, **self.pp_item.__dict__)
        self.curr_scene.addItem(new_btn)

        # Get the center of this new object and move it according to its dimensions.
        # So the new item will spawn at the center of itself.
        if set_pos:
            new_pos = self.convert_from_center(QtCore.QPointF(set_pos), new_btn)

        # Otherwise start at the center of the scene.
        else:
            new_pos = self.convert_from_center(QtCore.QPointF(0, 0), new_btn)

        new_btn.setPos(new_pos)

    def update_btn(self, sel_items=None):
        """
        Updates the selected picker.

        :param sel_items: The GraphicsButtons to work on.
        :type: list
        """
        # Usually just takes whatever is selected if it wasn't passed in.
        if not sel_items:
            sel_items = self.curr_scene.selectedItems()
            if not sel_items:
                return None

        for item in sel_items:

            # Set the current shape.
            item.curr_shape = copy.deepcopy(self.pp_item.curr_shape)

            # Grab the old rect and use it to make a new QRect to update the current
            # selected GraphicsItem's bounding rect. Calculate the new position using the
            # old center and move it after updating the bounding rect.
            old_center = self.get_center(item)
            old_rect = item.set_rect
            item.update_bounding_rect(QtCore.QRect(old_rect.x(), old_rect.y(),
                                                   self.pp_item.set_rect.width(),
                                                   self.pp_item.set_rect.height()))
            new_pos = self.convert_from_center(old_center, item)
            item.setPos(new_pos)

            # Update the polygon.
            new_polygon_coords = copy.deepcopy(self.pp_item.curr_coords)
            item.update_polygon(new_polygon_coords)

            # And then update the other properties.
            item.update_text(self.pp_item.text)
            pp_item_col = self.pp_item.brush
            item.update_brush_color(pp_item_col)
            item.highlight_button(False)

        # Clear the current selection of the current scene.
        self.curr_scene.clearSelection()

    def update_btn_selection(self, sel_items=None):
        """
        Updates the selected button's selected objects.

        :param sel_items: The graphics items to work on.
        :type: list
        """
        # Usually just takes whatever is selected if it wasn't passed in.
        if not sel_items:
            sel_items = self.curr_scene.selectedItems()
            if not sel_items:
                return None

        for item in sel_items:
            # TODO: Filter the selection in Maya for specific types of objects.
            # Possibly filter out meshes and stuff like that.
            curr_sel = cmds.ls(selection=True)
            item.update_sel_list(curr_sel)

        self.update_tree_view()

    def delete_btn(self, sel_items=None):
        """
        Deletes the graphics button from the graphics scene.

        :param sel_items: The graphics items to work on.
        :type: list
        """
        # Usually just takes whatever is selected if it wasn't passed in.
        if not sel_items:
            sel_items = self.curr_scene.selectedItems()
            if not sel_items:
                return None

        for item in sel_items:
            self.curr_scene.removeItem(item)

    def take_screenshot(self):
        """
        Saves the flags of the current playblast camera, take a screenshot, and add it
        as a pixmapitem to the current scene.
        """
        # Save the flags of the current panel that will be used for the playblast.
        curr_panel = cmds.playblast(activeEditor=True)
        orig_flags = cmds.modelEditor(curr_panel, query=True, stateString=True)
        orig_flags = ("$editorName = \"%s\";\n" % curr_panel) + orig_flags

        # Isolate the view to just the polygons.
        set_flag = False
        cmds.modelEditor(curr_panel, edit=True, allObjects=set_flag,
                         selectionHiliteDisplay=set_flag,
                         manipulators=set_flag,
                         headsUpDisplay=set_flag,
                         hulls=set_flag,
                         grid=set_flag,
                         holdOuts=set_flag)
        cmds.modelEditor(curr_panel, edit=True, polymeshes=True)

        # Check if the folder of the tab exists.
        curr_tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex())
        working_dir = PickerToolEnums.WORKING_DIR
        tab_file_dir = os.path.join(working_dir, PickerToolEnums.IMG_FOLDER,
                                    curr_tab_name)
        if not os.path.exists(tab_file_dir):
            try:
                os.makedirs(tab_file_dir, exist_ok=True)
            except WindowsError:
                mel.eval(orig_flags)
                print("Unable to make tab file directory.")
                return None

        # Get the current screenshots in the folder, only pngs following the naming
        # convention.
        screenshot_files = [f for f in os.listdir(tab_file_dir) if \
                            os.path.isfile(os.path.join(tab_file_dir, f)) and \
                            ("%s_" % PickerToolEnums.SCREENSHOT_PREFIX) in f]

        # Start from 1 and search the directory for the next increment that we can name.
        version_set = False
        count = 1
        output_file = ""
        while version_set is False:
            output_file = ("%s_%03d" % (PickerToolEnums.SCREENSHOT_PREFIX, count)) + \
                           "." + PickerToolEnums.SCREENSHOT_EXT
            if output_file in screenshot_files:
                version_set = False
                count += 1
            else:
                version_set = True

        # Create the new file name.
        output_file = os.path.join(tab_file_dir, output_file)

        # Playblast a png to a directory.
        output = cmds.playblast(
            completeFilename=output_file,
            forceOverwrite=True, format="image", startTime=1, endTime=1, quality=100,
            viewer=False, frame=[1]
        )

        # Create a pixmap item and add it.
        pixmap = GraphicsPixmap(image=output)
        self.curr_scene.addItem(pixmap)
        pixmap.setZValue(-1.0)

        # Reset the view to the flags before the playblast.
        mel.eval(orig_flags)

        print("Saved img to: %s" % output_file)

    def create_selected_objs_layout(self):
        """
        Creates the selected objects list view and its label into a neat layout.

        :return: A layout with the selected objects view and its label.
        :type: QtWidgets.QVBoxLayout
        """
        main_vb = QtWidgets.QVBoxLayout()

        # Make the Selected Objects label.
        sel_objs_label = QtWidgets.QLabel("Selected Objects:")
        main_vb.addWidget(sel_objs_label)

        # Make the Selected Objects list widget.
        self.sel_objs_list_view = QtWidgets.QTreeWidget()
        self.sel_objs_list_view.setHeaderHidden(True)
        self.sel_objs_list_view.setMinimumSize(200, 200)
        main_vb.addWidget(self.sel_objs_list_view)

        return main_vb

    def update_tree_view(self):
        """
        Updates the tree view after selection.
        """
        # Clear the currentn list view and get the scene's selected items.
        self.sel_objs_list_view.clear()
        sel_item = self.curr_scene.selectedItems()

        # Iterate through the selected items.
        for item in sel_item:

            if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                continue

            ctrl_items = item.sel_objs

            # Get the color from the selected item, and reduce the value, from the HSV.
            ctrl_col = QtGui.QColor(item.brush_col.color().rgb())
            ctrl_col.setHsv(ctrl_col.hue(), ctrl_col.saturation(),
                            ctrl_col.value() / 2, 255)

            # If the selected item has no controls to select, then display no controls.
            if not ctrl_items or ctrl_items == []:
                filler_item = QtWidgets.QTreeWidgetItem(self.sel_objs_list_view,
                                                        [PickerToolEnums.NO_CTRLS_MSG])
                filler_item.setBackgroundColor(0, ctrl_col)
            else:
                for sel_item in ctrl_items:
                    sel_tree_item = QtWidgets.QTreeWidgetItem(self.sel_objs_list_view, \
                                                              [sel_item])
                    sel_tree_item.setBackgroundColor(0, ctrl_col)

    def get_center(self, item=None):
        """
        Gets the center of the item in scene coordinates.

        :return: The QPointF of the center of the item.
        :type: QtCore.QPointF
        """
        if not item:
            return None

        # Get the bounding rect of the button.
        rect = item.set_rect
        item_pos = item.scenePos()

        # Divide the width and height in half and use that to be the center.
        x_dist = rect.width()/2.0
        y_dist = rect.height()/2.0
        x_center = item_pos.x() + x_dist
        y_center = item_pos.y() + y_dist

        return QtCore.QPointF(x_center, y_center)


    def convert_from_center(self, center=None, item=None):
        """
        Converts the given position to the item's top left corner.

        :param center: The center of the given item.
        :type: QtCore.QPointF

        :param item: The item to find the coordinate of.
        :type: GraphicsButton

        :return: The QPointF of the the item.
        :type: QtCore.QPointF
        """
        if center is None or not item:
            return None

        # Get the bounding rect of the button and calculate the distance from the center.
        rect = item.set_rect
        x_dist = rect.width()/2.0
        y_dist = rect.height()/2.0

        # Subtract the halfway distance from the center to get the top left corner coord.
        x_new = center.x() - x_dist
        y_new = center.y() - y_dist

        return QtCore.QPointF(x_new, y_new)

    def get_average_coord(self, items=None):
        """
        Calculates the average coordinates out of the selection.

        :param items: The items we'll use to calculate the average.
        :type: list

        :return: The average coordinates in scene space.
        :type: QtCore.QPointF
        """
        if not items:
            return None

        total_x = 0.0
        total_y = 0.0
        for item in items:
            item_center = self.get_center(item)
            total_x += item_center.x()
            total_y += item_center.y()

        x_average = total_x / len(items)
        y_average = total_y / len(items)

        return QtCore.QPointF(x_average, y_average)

    def replace_pixmap(self, pixmap_item=None):
        """
        Opens a dialog so the user can fix/replace their images.
        """
        if not pixmap_item:
            return None

        # Open a dialog and get a new file path.
        filename, ffilter = QtWidgets.QFileDialog.getOpenFileName(caption="Load File",
                                        dir=os.path.join(PickerToolEnums.WORKING_DIR,
                                                         PickerToolEnums.IMG_FOLDER),
                                        filter="PNG (*.png)")
        if not filename:
            return None
        if not os.path.exists(filename):
            print("Invalid file path")
            return None

        new_pixmap = QtGui.QPixmap(filename)
        pixmap_item.setPixmap(new_pixmap)


class SaveTabsDialog(QtWidgets.QDialog):
    """
    Window for setting which tabs to export.
    """
    save_as_clicked = QtCore.Signal(list)

    def __init__(self):
        QtWidgets.QDialog.__init__(self, parent=get_maya_window())

    def init_gui(self, tab_widget=None):
        """
        Populates the window and shows it.
        """
        # Ensure we have the tab widget to work with.
        if not tab_widget:
            return None

        main_vb = QtWidgets.QVBoxLayout(self)

        # Make the tree widget.
        self.tab_tree_widget = QtWidgets.QTreeWidget()
        main_vb.addWidget(self.tab_tree_widget)

        dialog_lbl = QtWidgets.QLabel("Choose which tabs to export")
        main_vb.addWidget(dialog_lbl)

        # Add each tab as an option to export.
        for tab_index in range(tab_widget.count()):
            tab_name = tab_widget.tabText(tab_index)
            entry = QtWidgets.QTreeWidgetItem(self.tab_tree_widget,
                                              [tab_name])
            entry.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            entry.setData(0, QtCore.Qt.CheckStateRole, QtCore.Qt.Unchecked)
            entry.setCheckState(0, QtCore.Qt.Checked)

        # Change the checkbox colors and hide the header.
        tree_palette = QtGui.QPalette()
        tree_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(200, 200, 200))
        self.tab_tree_widget.setPalette(tree_palette)
        self.tab_tree_widget.setHeaderHidden(True)

        # Check All or Check None boxes.
        check_hb = QtWidgets.QHBoxLayout()
        check_all_btn = QtWidgets.QPushButton("Check All")
        check_all_btn.clicked.connect(self.check_all_clicked)
        uncheck_all_btn = QtWidgets.QPushButton("Uncheck All")
        uncheck_all_btn.clicked.connect(self.uncheck_all_clicked)
        check_hb.addWidget(check_all_btn)
        check_hb.addWidget(uncheck_all_btn)
        main_vb.addLayout(check_hb)

        # Save and Cancel button.
        bottom_hb = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.clicked.connect(self.save_as)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        bottom_hb.addWidget(save_btn)
        bottom_hb.addWidget(cancel_btn)
        main_vb.addLayout(bottom_hb)

        self.setGeometry(960, 540, 200, 200)
        self.setWindowTitle("Save As...")
        self.show()

    def verify_tree(self):
        """
        Verifies there is data of the tree view.

        :return: The root item of the tree and the number of children.
        :type: QtWidgets.QTreeWidgetItem and int
        """
        root = self.tab_tree_widget.invisibleRootItem()
        child_count = root.childCount()

        # If there are no tabs, do nothing.
        if child_count < 1:
            return None
        return root, child_count

    def check_all_clicked(self):
        """
        Checks all the check boxes in the tree view.
        """
        root, child_count = self.verify_tree()
        if not root or not child_count:
            return None

        for item_row in range(child_count):
            item = root.child(item_row)
            if item.checkState(0):
                continue
            else:
                item.setCheckState(0, QtCore.Qt.Checked)

    def uncheck_all_clicked(self):
        """
        Unchecks all the check boxes in the tree view.
        """
        root, child_count = self.verify_tree()
        if not root or not child_count:
            return None

        for item_row in range(child_count):
            item = root.child(item_row)
            if not item.checkState(0):
                continue
            else:
                item.setCheckState(0, QtCore.Qt.Unchecked)

    def save_as(self):
        """
        User selects the save. Create a list to emit the save signal back to the main wnd.
        """
        # Gathers up all of the selected items.
        root = self.tab_tree_widget.invisibleRootItem()
        child_count = root.childCount()

        send_list = []
        for item_row in range(child_count):
            item = root.child(item_row)
            if item.checkState(0):
                send_list.append(item_row)

        self.save_as_clicked.emit(send_list)
        self.close()


class MirrorSettingsDialog(QtWidgets.QMainWindow):
    """
    The window for setting mirror settings.
    """
    def __init__(self, main_wnd):
        QtWidgets.QMainWindow.__init__(self, parent=get_maya_window())

        self.main_wnd = main_wnd

        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint)

        # Radio button row for which axis to mirror on. Starts X as true.
        self.x_rdbtn = QtWidgets.QRadioButton("X")
        self.x_rdbtn.setChecked(True)
        self.x_rdbtn.setAutoExclusive(False)
        self.y_rdbtn = QtWidgets.QRadioButton("Y")
        self.y_rdbtn.setAutoExclusive(False)

        # Add the mirror on combo box. Starts on the world.
        self.mirror_on_combo = QtWidgets.QComboBox()
        self.mirror_on_combo.addItems(PickerToolEnums.MIRROR_ONS)
        self.mirror_on_combo.setCurrentText(PickerToolEnums.MIRROR_ONS[0])

        # Add the type combo box. Starts at Duplicate.
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(PickerToolEnums.MIRROR_TYPES)
        self.type_combo.setCurrentText(PickerToolEnums.MIRROR_TYPES[0])

    def init_gui(self):
        """
        We don't show the GUI in the init, so this function creates the necessary
        elements and shows the dialog.
        """
        outer_widget = QtWidgets.QWidget()
        outer_vb = QtWidgets.QVBoxLayout()
        container_widget = QtWidgets.QWidget()

        main_form_layout = QtWidgets.QFormLayout()

        # The Radio button row for which axis to mirror on.
        radio_axis_hb = QtWidgets.QHBoxLayout()
        radio_axis_hb.addWidget(self.x_rdbtn)
        radio_axis_hb.addWidget(self.y_rdbtn)
        main_form_layout.addRow("Mirror Axis:", radio_axis_hb)

        # The mirror on combo box row.
        main_form_layout.addRow("Mirror Across:", self.mirror_on_combo)

        # The type combo box row.
        main_form_layout.addRow("Mirror Type:", self.type_combo)

        # Add the main form layout to the container widget, then add it to the outer vb.
        container_widget.setLayout(main_form_layout)
        outer_vb.addWidget(container_widget)

        # Add a stretch then the bottom hb to give distance like a Maya properties window.
        outer_vb.addStretch(1)
        bottom_hb = self.create_bottom_hb()
        outer_vb.addLayout(bottom_hb)

        outer_widget.setLayout(outer_vb)
        self.setCentralWidget(outer_widget)

        self.create_context_menu()

        self.setGeometry(960, 540, 300, 200)
        self.setWindowTitle("Mirror Settings")
        self.show()

    def create_context_menu(self):
        """
        Creates the dialog's context menu.

        :return: The menu to add to the dialog.
        :type: QtWidgets.QMenu
        """
        main_menu = QtWidgets.QMenuBar()

        edit_menu = main_menu.addMenu("Edit")

        reset_act = QtWidgets.QAction("Reset Defaults", self)
        reset_act.triggered.connect(self.reset_defaults)
        edit_menu.addAction(reset_act)

        self.setMenuBar(main_menu)

    def reset_defaults(self):
        """
        Resets the GUI elements to defaults.
        """
        self.x_rdbtn.setChecked(True)
        self.y_rdbtn.setChecked(False)
        self.mirror_on_combo.setCurrentText(PickerToolEnums.MIRROR_ONS[0])
        self.type_combo.setCurrentText(PickerToolEnums.MIRROR_TYPES[0])

    def create_bottom_hb(self):
        """
        Creates the bottom buttons.

        :return: The bottom buttons horizontal layout.
        :type: QtWidgets.QHBoxLayout
        """
        main_hb = QtWidgets.QHBoxLayout()

        mirror_btn = QtWidgets.QPushButton("Apply and close")
        mirror_btn.clicked.connect(self.apply_close_clicked)
        main_hb.addWidget(mirror_btn)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_clicked)
        main_hb.addWidget(apply_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        main_hb.addWidget(cancel_btn)

        return main_hb


    def apply_close_clicked(self):
        """
        Use the main window's mirror function and close this dialog.
        """
        self.main_wnd.mirror_sel_btns()
        self.close()

    def apply_clicked(self):
        """
        Use the main window's mirror function.
        """
        self.main_wnd.mirror_sel_btns()

