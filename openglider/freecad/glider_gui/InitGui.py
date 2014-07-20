import FreeCADGui as Gui

Gui.addIconPath(FreeCAD.getHomePath() + "Mod/glider_gui/icons")

from objects import CreateLine, CreateSpline, Airfoil, CreateShape, Base_Tool

Gui.addCommand('CreateLine', CreateLine())
Gui.addCommand('Base_Tool', Base_Tool())
# Gui.addCommand('CreateSpline', CreateSpline())
# Gui.addCommand('Airfoil', Airfoil())
# Gui.addCommand('CreateShape', CreateShape())

class gliderWorkbench(Workbench):
    """probe workbench object"""
    MenuText = "glider"
    ToolTip = "glider workbench"
    Icon = "glider_workbench.svg"

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def Initialize(self):
        profileitems = ["CreateLine", "Base_Tool"]
        self.appendToolbar("test", profileitems)
        self.appendMenu("test", profileitems)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

Gui.addWorkbench(gliderWorkbench())