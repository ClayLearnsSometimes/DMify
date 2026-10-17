from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter, QListWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from pathlib import Path

import diceCalculator as diceCalculator

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
window.setWindowTitle("DMify: D&D Reference Browser")

# clicking a sidebar item loads a page
def open_page(item):
    filename = item.text().lower() + ".html"
    if item.text() == "Fireball":
        filename = "pages/spell-fireball.html"
    elif item.text() == "Goblin":
        filename = "pages/goblin.html"
    browser.setUrl(QUrl.fromLocalFile(str(Path(filename).resolve())))

sidebar.itemClicked.connect(open_page)

browser.setUrl(QUrl.fromLocalFile(str(Path("pages/goblin.html").resolve())))
window.show()
app.exec()