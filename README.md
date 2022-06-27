# Picker Tool
A rigging and animation tool for creating and animating with pickers.

## Requirements
Runs on Maya 2022+ - Python 3.7.

## Features
- Node Editor-like graphics scenes for intuitive navigation and selecting in picker windows.
- Picker Preview to visually create buttons in real-time before adding to the main scenes.
- Saving out pickers to readable XML files.
- Load XML files for animating or editing.
- Custom shapes by drawing from Maya's nurbsCurves.
- Custom shapes can have varying precision to reduce XML file sizes or meet exact control shapes.
- Buttons can have labels, virtually unlimited color options, and customizable width and heights.
- Scene-edit options such as alignment, search and rename labels, smart and varied mirroring.
- Take a screenshot from the playblast camera on the view, and it's saved along with the XML files.
- Multiple tabs.
- Namespaces considered when selecting buttons and Maya controls.
- Toggle editing modes and editing menus.

## How to Run
Unzip and drop the picker tool directory to your maya scripts directory. For example, in Maya 2022 the scripts directory will be in:
C:\Users\(username)\Documents\maya\2022\scripts
![image](https://user-images.githubusercontent.com/70284366/175859590-d97f5096-f516-43c8-ba09-54e3cfc2f351.png)

Within Maya, run the following line in the script editor, and save it as a shelf button if you wish:

import picker_tool.picker_gui as pg
gui = pg.PickerWindow()
gui.init_gui()

![image](https://user-images.githubusercontent.com/70284366/175860041-77902985-0f49-418a-99b7-cf1e96f5e56d.png)

