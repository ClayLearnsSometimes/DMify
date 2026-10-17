from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter, QListWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from pathlib import Path

app = QApplication([])

# the two panels
sidebar = QListWidget()
sidebar.addItem("Fireball")
sidebar.addItem("Goblin")

browser = QWebEngineView()

# put them side by side in a splitter
splitter = QSplitter()
splitter.addWidget(sidebar)
splitter.addWidget(browser)
splitter.setStretchFactor(0, 1)   # sidebar gets 1 part
splitter.setStretchFactor(1, 2)   # browser gets 2 parts

# the main window holds the splitter
window = QMainWindow()
window.setCentralWidget(splitter)
window.resize(1200, 700)

# clicking a sidebar item loads a page
def open_page(item):
    filename = item.text().lower() + ".html"
    if item.text() == "Fireball":
        filename = "clean_pages/feat-dual-wielder.html"
    browser.setUrl(QUrl.fromLocalFile(str(Path(filename).resolve())))

sidebar.itemClicked.connect(open_page)

browser.setUrl(QUrl.fromLocalFile(str(Path("testFile.html").resolve())))
window.show()
app.exec()