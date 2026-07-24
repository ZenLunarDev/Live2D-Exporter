# Copyright (c) 2023 Meptl
# Copyright (c) 2026 กรมท
# SPDX-License-Identifier: MIT

from krita import Krita, Extension, InfoObject
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
import os

def visibleTopLevelNodes(doc):
    if doc is None:
        return []
    for node in doc.topLevelNodes():
        if node.visible():
            yield node


def forFlatGroupLeafs(doc, node, func):
    if node.type() != "grouplayer":
        return

    has_group = False
    for n in node.childNodes():
        if n.type() == "grouplayer":
            forFlatGroupLeafs(doc, n, func)
            has_group = True

    if not has_group:
        doc.setActiveNode(node)
        func(doc, node)


def forLeafs(node, func):
    if len(node.childNodes()) == 0:
        func(node)
    else:
        for n in node.childNodes():
            forLeafs(n, func)


def addGroupWithSameName(doc, node):
    Krita.instance().action("create_quick_group").trigger()
    doc.waitForDone()
    node.parentNode().setName(node.name())


def removeMergedSuffix(node):
    if node.name().endswith(" Merged"):
        node.setName(node.name()[:-7])


def mergeLeaf(doc, node):
    Krita.instance().action("merge_layer").trigger()
    doc.waitForDone()
    doc.refreshProjection()
    QApplication.processEvents()


def save_as_psd(node):
    application = Krita.instance()
    window = application.activeWindow()
    currentDoc = application.activeDocument()

    if currentDoc is None or window is None:
        return

    currentView = window.activeView()
    currentDoc.setActiveNode(node)
    application.action("edit_copy").trigger()
    currentDoc.waitForDone()

    bounds = node.bounds()
    if bounds.isEmpty():
        return

    newDoc = application.createDocument(
        int(bounds.width()),
        int(bounds.height()),
        node.name() + ".psd",
        currentDoc.colorModel(),
        currentDoc.colorDepth(),
        currentDoc.colorProfile(),
        currentDoc.resolution()
    )
    window.addView(newDoc)
    application.setActiveDocument(newDoc)
    default_layer = newDoc.topLevelNodes()[0]
    application.action("edit_paste").trigger()
    default_layer.remove()
    newDoc.waitForDone()
    newDoc.refreshProjection()

    current_path = currentDoc.fileName()
    if current_path:
        outfile = os.path.join(os.path.dirname(current_path),
                               node.name() + ".psd")
        newDoc.saveAs(outfile)
        print(f'Saving {outfile}')
    newDoc.close()

    application.setActiveDocument(currentDoc)
    currentDoc.setActiveNode(node)

class Live2DExporterExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)


    def setup(self):
        pass


    def createActions(self, window):
        action = window.createAction("live2d_export",
                                     "Live2D Export",
                                     "tools/scripts")
        action.triggered.connect(self.live2d_export)


    def showErrorWindow(self, message):
        dialog = QDialog()
        dialog.setWindowTitle("Operation Failed")
        layout = QVBoxLayout()
        label = QLabel()
        label.setText(message)
        layout.addWidget(label)
        button = QPushButton("OK")
        button.clicked.connect(lambda: dialog.close())
        layout.addWidget(button)
        dialog.setLayout(layout)
        dialog.exec_()


    def live2d_export(self):
        application = Krita.instance()
        currentDoc = application.activeDocument()

        if currentDoc is None:
            self.showErrorWindow("No active document found.")
            return

        if currentDoc.modified():
            self.showErrorWindow("Current document has unsaved changes. Aborting operation.")
            return

        if currentDoc.fileName() is None:
            self.showErrorWindow("Current document has not been saved. Please save it first.")
            return

        node_names = [n.name() for n in visibleTopLevelNodes(currentDoc)]
        if len(node_names) != len(set(node_names)):
            self.showErrorWindow("There are multiple top-level layers that share a name. Aborting operation.")
            return

        for node in visibleTopLevelNodes(currentDoc):
            forFlatGroupLeafs(currentDoc, node, addGroupWithSameName)

        for node in visibleTopLevelNodes(currentDoc):
            forFlatGroupLeafs(currentDoc, node, mergeLeaf)

        for node in visibleTopLevelNodes(currentDoc):
            forLeafs(node, removeMergedSuffix)

        for node in visibleTopLevelNodes(currentDoc):
            save_as_psd(node)

        currentDoc.setModified(False)
