# test_imports.py
import importlib

modules = [
    "careerbuddy.ui.tracker",
    "careerbuddy.ui.catcher",
    "careerbuddy.ui.calendar",
    "careerbuddy.ui.analytics",
    "careerbuddy.ui.coverletter",
    "careerbuddy.ui.filevault",
    "careerbuddy.ui.whiteboard",
    "careerbuddy.ui.notepad",
    "careerbuddy.ui.aibuddy",
]

for name in modules:
    print("Importing", name, "...", end=" ")
    importlib.import_module(name)
    print("OK")
