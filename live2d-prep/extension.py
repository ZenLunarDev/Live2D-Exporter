from krita import Krita, Extension, InfoObject
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication, QMessageBox
import os
import time
import datetime
import traceback


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_PATH = os.path.join(_SCRIPT_DIR, "live2d-prep.log")


def log(msg):
    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] {msg}"
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


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
    except Exception as e:
        log(f"addGroup ERROR: {e}")


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
    except Exception as e:
        log(f"merge ERROR: {e}")


def sanitizeFilename(name):
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, '_')
    return name.strip() or "untitled"


class _SaveTask:
    def __init__(self, doc, node, outfile):
        self.doc = doc
        self.node = node
        self.outfile = outfile
        self.export_doc = None
        self.export_view = None
        self.finished = False
        self.success = False

    def run(self):
        if self.doc is None or self.node is None or not self.outfile:
            self.finished = True
            self.success = False
            return

        try:
            bounds = self.node.bounds()
            if bounds.isEmpty():
                log(f"save SKIP empty bounds node={self.node.name()}")
                self.finished = True
                self.success = False
                return

            width = int(bounds.width())
            height = int(bounds.height())
            log(f"save START node={self.node.name()} {width}x{height}")

            log("save BEFORE createDocument")
            self.export_doc = Krita.instance().createDocument(
                width,
                height,
                self.node.name(),
                self.doc.colorModel(),
                self.doc.colorDepth(),
                self.doc.colorProfile(),
                self.doc.resolution(),
            )
            log("save AFTER createDocument")

            log("save BEFORE addView")
            view = Krita.instance().activeWindow().addView(self.export_doc)
            self.export_view = view
            log("save AFTER addView")

            log("save BEFORE setActiveDocument export")
            Krita.instance().setActiveDocument(self.export_doc)
            log("save AFTER setActiveDocument export")

            log("save BEFORE copy")
            self.doc.setActiveNode(self.node)
            Krita.instance().action("edit_copy").trigger()
            self.doc.waitForDone()
            log("save AFTER copy")

            log("save BEFORE paste")
            Krita.instance().action("edit_paste").trigger()
            self.export_doc.waitForDone()
            self.export_doc.refreshProjection()
            log("save AFTER paste")

            log("save BEFORE remove default layer")
            root_nodes = self.export_doc.topLevelNodes()
            if root_nodes:
                root_nodes[0].remove()
            log("save AFTER remove default layer")

            log("save BEFORE setActiveDocument current")
            Krita.instance().setActiveDocument(self.doc)
            self.doc.setActiveNode(self.node)
            log("save AFTER setActiveDocument current")

            log("save BEFORE delay")
            for _ in range(10):
                time.sleep(0.03)
                QApplication.processEvents()
            log("save AFTER delay")

            log("save BEFORE saveAs")
            saved = self.export_doc.saveAs(self.outfile)
            self.export_doc.waitForDone()
            QApplication.processEvents()
            log(f"save AFTER saveAs saved={saved} exists={os.path.exists(self.outfile)}")

            if saved and os.path.exists(self.outfile):
                self.success = True
            else:
                self.success = False
        except Exception as e:
            log(f"save EXCEPTION: {e}")
            log(traceback.format_exc())
            self.success = False
        finally:
            try:
                if self.export_view is not None:
                    self.export_view.close()
            except Exception:
                pass
            try:
                if self.export_doc is not None:
                    self.export_doc.close()
            except Exception:
                pass
            self.export_doc = None
            self.export_view = None
            Krita.instance().setActiveDocument(self.doc)
            self.doc.setActiveNode(self.node)
            self.finished = True


class Live2DExporterExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("live2d_export", "Live2D Export", "tools/scripts")
        action.triggered.connect(self.live2d_export)

    def showErrorWindow(self, message):
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Critical)
        dialog.setWindowTitle("Operation Failed")
        dialog.setText(message)
        dialog.exec_()

    def showInfoWindow(self, message):
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Information)
        dialog.setWindowTitle("Operation Complete")
        dialog.setText(message)
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
            self.showErrorWindow("Duplicate top-level layer names detected.")
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
                    errors.append(f"group ERROR '{node.name()}': {e}")
                    log(traceback.format_exc())

            for node in visible_nodes:
                try:
                    forFlatGroupLeafs(currentDoc, node, mergeLeaf)
                except Exception as e:
                    errors.append(f"merge ERROR '{node.name()}': {e}")
                    log(traceback.format_exc())

            for node in visible_nodes:
                try:
                    forLeafs(node, removeMergedSuffix)
                except Exception as e:
                    errors.append(f"clean ERROR '{node.name()}': {e}")
                    log(traceback.format_exc())

            for node in visible_nodes:
                out_dir = os.path.dirname(currentDoc.fileName()) or os.path.expanduser("~")
                outfile = os.path.join(out_dir, node.name() + ".psd")
                task = _SaveTask(currentDoc, node, outfile)
                task.run()

                while not task.finished:
                    QApplication.processEvents()

                if task.success:
                    success_count += 1
                else:
                    errors.append(f"export FAIL '{node.name()}'")

            currentDoc.setModified(False)

        except Exception as e:
            errors.append(f"UNEXPECTED ERROR: {e}")
            log(traceback.format_exc())

        msg_parts = []
        if success_count > 0:
            msg_parts.append(f"Successfully exported {success_count} file(s).")
        if errors:
            msg_parts.append(f"\nErrors ({len(errors)}):")
            for err in errors:
                msg_parts.append(f"• {err}")

        if msg_parts:
            self.showInfoWindow("".join(msg_parts))
