from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QSplitter, QListWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from pathlib import Path
import ctypes

import diceCalculator as diceCalculator
import wisper as speech
app = QApplication([])

# WINDOWS TASKBAR FIX: Force Windows to register DMify as a unique app
myappid = "DMify"  # A unique string identifier
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# the two panels
#this side bar holds 20-22 items nicely with room for a mic toggle thing
sidebar = QListWidget()
sidebar.addItem("Welcome")
sidebar.addItem("Sorcerer")
sidebar.addItem("Fireball")
sidebar.addItem("Goblin")
sidebar.addItem("Spells")
sidebar.addItem("Divine Smite")
sidebar.addItem("Halfling")


browser = QWebEngineView()
#button = QPushButton("Roll 2d8")

#button.clicked.connect(lambda: diceCalculator.roll(2, 8))

# put them side by side in a splitter
splitter = QSplitter()
splitter.addWidget(sidebar)
splitter.addWidget(browser)
#splitter.addWidget(button)
splitter.setStretchFactor(0, 1)   # sidebar gets 1 part
splitter.setStretchFactor(1, 2)   # browser gets 2 parts

# the main window holds the splitter
window = QMainWindow()
window.setCentralWidget(splitter)
window.resize(1200, 700)
window.setWindowIcon(QIcon("icon.png"))
window.setWindowTitle("DMify: D&D Reference Browser")

#browser.setURL(QUrl.fromLocalFile(str(Path("welcome.html").resolve())))

# clicking a sidebar item loads a page
def open_page(item):
    filename = item.text().lower() + ".html"
    if item.text() == "Welcome":
            filename = "welcome/welcome.html"
    elif item.text() == "Fireball":
        filename = "pages/spell-fireball.html"
    elif item.text() == "Goblin":
        filename = "pages/goblin.html"
    elif item.text() == "Sorcerer":
        filename = "pages/sorcerer.html"
    elif item.text() == "Fireball":
       filename = "pages/spell-fireball.html"
    elif item.text() == "Spells":
        filename = "pages/spells.html"
    elif item.text() == "Divine Smite":
        filename = "pages/spell-divine-smite.html"
    elif item.text() == "Halfling":
        filename = "pages/halfling-athas.html"
    browser.setUrl(QUrl.fromLocalFile(str(Path(filename).resolve())))

sidebar.itemClicked.connect(open_page)

browser.setUrl(QUrl.fromLocalFile(str(Path("welcome/welcome.html").resolve())))
window.show()
app.exec()

