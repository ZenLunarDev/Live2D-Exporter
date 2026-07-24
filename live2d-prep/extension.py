from krita import Krita, Extension, InfoObject
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
import os
import time
import traceback


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
    try:
        Krita.instance().action("create_quick_group").trigger()
        doc.waitForDone()
        QApplication.processEvents()

        parent = node.parentNode()
        if parent is not None:
            parent.setName(node.name())
    except Exception as e:
        print(f"Failed to add group: {e}")


def removeMergedSuffix(node):
    name = node.name()
    if name.endswith(" Merged"):
        node.setName(name[:-7])


def mergeLeaf(doc, node):
    try:
        doc.setActiveNode(node)
        Krita.instance().action("merge_layer").trigger()
        doc.waitForDone()
        doc.refreshProjection()
        QApplication.processEvents()
    except Exception as e:
        print(f"Failed to merge: {e}")


def sanitizeFilename(name):
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, '_')
    return name.strip() or "untitled"


def killExtraViews(window):
    try:
        if window is None:
            return
        for w in window.workspace().windows():
            for v in w.views():
                pass
    except Exception:
        pass


def save_as_psd(node):
    application = Krita.instance()
    window = application.activeWindow()
    currentDoc = application.activeDocument()

    if currentDoc is None or window is None or node is None:
        return False

    old_active = application.activeDocument()

    try:
        currentDoc.setActiveNode(node)
        application.action("edit_copy").trigger()
        currentDoc.waitForDone()
        QApplication.processEvents()

        bounds = node.bounds()
        if bounds.isEmpty():
            return False

        short_name = sanitizeFilename(node.name())

        export_doc = application.createDocument(
            int(bounds.width()),
            int(bounds.height()),
            short_name + ".psd",
            currentDoc.colorModel(),
            currentDoc.colorDepth(),
            currentDoc.colorProfile(),
            currentDoc.resolution()
        )

        window.addView(export_doc)
        application.setActiveDocument(export_doc)
        QApplication.processEvents()

        default_layer = export_doc.topLevelNodes()[0]
        application.action("edit_paste").trigger()
        export_doc.waitForDone()
        export_doc.refreshProjection()
        QApplication.processEvents()

        default_layer.remove()

        current_path = currentDoc.fileName()
        out_dir = os.path.dirname(current_path) if current_path else os.path.expanduser("~")

        outfile = os.path.join(out_dir, short_name + ".psd")

        saved = export_doc.saveAs(outfile)
        export_doc.waitForDone()

        time.sleep(0.05)
        QApplication.processEvents()

        if not saved or not os.path.exists(outfile):
            print(f"save failed/not found: {outfile}")
            return False

        print(f"Saved: {outfile}")
        return True

    finally:
        QApplication.processEvents()

        try:
            if 'export_doc' in locals() and export_doc is not None:
                export_doc.close()
        except Exception as e:
            print(f"close doc err: {e}")

        time.sleep(0.05)
        QApplication.processEvents()

        try:
            if old_active is not None and old_active is not currentDoc:
                application.setActiveDocument(old_active)
            else:
                application.setActiveDocument(currentDoc)
            currentDoc.setActiveNode(node)
        except Exception as e:
            print(f"restore doc err: {e}")

        QApplication.processEvents()
        killExtraViews(window)


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
        label.setWordWrap(True)
        layout.addWidget(label)
        button = QPushButton("OK")
        button.clicked.connect(dialog.close)
        layout.addWidget(button)
        dialog.setLayout(layout)
        dialog.exec_()

    def showInfoWindow(self, message):
        dialog = QDialog()
        dialog.setWindowTitle("Operation Complete")
        layout = QVBoxLayout()
        label = QLabel()
        label.setText(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        button = QPushButton("OK")
        button.clicked.connect(dialog.close)
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
            self.showErrorWindow("Current document has unsaved changes. Please save your document first.")
            return

        if not currentDoc.fileName():
            self.showErrorWindow("Current document has not been saved. Please save it first.")
            return

        visible_nodes = list(visibleTopLevelNodes(currentDoc))
        node_names = [n.name() for n in visible_nodes]
        if len(node_names) != len(set(node_names)):
            self.showErrorWindow("Duplicate top-level layer names detected. Each top-level layer must have a unique name.")
            return

        if len(visible_nodes) == 0:
            self.showErrorWindow("No visible top-level layers found to export.")
            return

        errors = []
        success_count = 0

        try:
            for node in visible_nodes:
                try:
                    forFlatGroupLeafs(currentDoc, node, addGroupWithSameName)
                except Exception as e:
                    errors.append(f"Error grouping layers in '{node.name()}': {e}")
                    print(traceback.format_exc())

            QApplication.processEvents()

            for node in visible_nodes:
                try:
                    forFlatGroupLeafs(currentDoc, node, mergeLeaf)
                except Exception as e:
                    errors.append(f"Error merging layers in '{node.name()}': {e}")
                    print(traceback.format_exc())

            QApplication.processEvents()

            for node in visible_nodes:
                try:
                    forLeafs(node, removeMergedSuffix)
                except Exception as e:
                    errors.append(f"Error cleaning names in '{node.name()}': {e}")
                    print(traceback.format_exc())

            QApplication.processEvents()

            for node in visible_nodes:
                try:
                    if save_as_psd(node):
                        success_count += 1
                    else:
                        errors.append(f"Failed to export '{node.name()}'")
                except Exception as e:
                    errors.append(f"Error exporting '{node.name()}': {e}")
                    print(traceback.format_exc())

                QApplication.processEvents()

            currentDoc.setModified(False)
            QApplication.processEvents()

        except Exception as e:
            errors.append(f"Unexpected error: {e}")
            print(traceback.format_exc())

        msg_parts = []
        if success_count > 0:
            msg_parts.append(f"Successfully exported {success_count} file(s).")
        if errors:
            msg_parts.append(f"\nErrors ({len(errors)}):")
            for err in errors:
                msg_parts.append(f"• {err}")

        if msg_parts:
            self.showInfoWindow("".join(msg_parts))
