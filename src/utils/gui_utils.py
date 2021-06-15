from utils import theme_dark
from PyQt5 import QtGui, QtWidgets
import os

def modify_property(handle, name, value):
    """ Modifies a CSS property of a given handle.

    :param handle: Qt object handle
        Handle that identifies the object to modify.
    :param name: basestring
        Name of the CSS property (e.g., 'color', 'font-size').
    :param value: basestring
        Value of the CSS property. Note that measurements must be specified, and ; is not required (e.g., '15px')
    """

    # Find if the property exists
    css_orig = handle.styleSheet()
    offset = 0
    css = css_orig
    while True:
        idx_1 = css.find(name + ":")
        if idx_1 == -1:
            # It does not exist, so append it
            prop = css_orig + name + ": " + value + ";"
            break

        idx_2 = css[idx_1:].find(";")
        if css.find("-" + name + ":") == -1:
            prop = css[idx_1:idx_1 + idx_2]
            idx_3 = prop.find(":")
            prop = css_orig[:offset + idx_1 + idx_3] + ": " + value + "; " + css_orig[offset + idx_1 + idx_2 + 1:]
            break
        else:
            # This was a property that contains the name but it is not the desired one. For instance, 'background-color'
            # contains 'color'
            css = css[idx_1 + idx_2:]
            offset += idx_1 + idx_2

    # Update the CSS
    handle.setStyleSheet(prop)
    return prop


def get_property(handle, name):
    """ Gets the value of a given CSS property in a handle.

    :param handle: Qt object handle
        Handle that identifies the object.
    :param name: basestring
        Name of the CSS property (e.g., 'color', 'font-size').
    """
    # Find if the property exists
    css = handle.styleSheet()

    # Find the appropriate property, not just one that contains the given name
    while True:
        idx_1 = css.find(name + ":")
        if idx_1 == -1:
            # It does not exist
            print(handle.styleSheet())
            raise ValueError('Property "%s" is not specified in %s.' % (name, handle))

        idx_2 = css[idx_1:].find(";")
        if css.find("-" + name + ":") == -1:
            value = css[idx_1:idx_1+idx_2]
            value = value.replace(name + ": ", "")  # Delete its name
            break
        else:
            # This was a property that contains the name but it not the desired one. For instance, 'background-color'
            # contains 'color'
            css = css[idx_1 + idx_2:]
    return value

# ---------------------------------------------- THEME DEFINITIONS ----------------------------------------------- #


def set_css_and_theme(gui_handle, css_path, theme):
    """ Reads the stylesheet and sets a theme.

    :param gui_handle: object
        Instance of the GUI.
    :param css_path: basestring
        Absolute path of the CSS file.
    :param theme: basestring
        Theme to select:
           'dark': Dark theme (i.e., darcula).
    :return stylesheet: basestring
        Gui stylesheet.
    """
    stl = load_stylesheet(css_path)
    stl = set_theme(stl, theme)
    gui_handle.setStyleSheet(stl)
    return stl


def load_stylesheet(path, charset='utf-8'):
    """ Loads and decodes a stylesheet in stylesheet parameter.

    :param path: basestring
        Absolute path of the CSS file.
    :param charset: basestring
        (Optional, default='utf-8') Decoding charset.

    :return stylesheet: basestring
        Decoded stylesheet
    """
    with open(path, "rb") as f:
        stl = f.read().decode(charset)
    return stl


def set_theme(stylesheet, theme='dark'):
    """ Sets a theme by replacing key string in the stylesheet.

    :param stylesheet: basestring
        Stylesheet to modify
    :param theme: basestring
        Theme selection:
            'dark': Dark theme (i.e., darcula).

    :return stylesheet: basestring
        Modified stylesheet
    """


    if theme == 'dark':
        stylesheet = stylesheet.replace('@THEME_BG_DARK', theme_dark.THEME_BG_DARK)
        stylesheet = stylesheet.replace('@THEME_BG_LIGHT', theme_dark.THEME_BG_LIGHT)
        stylesheet = stylesheet.replace('@THEME_BG_MID', theme_dark.THEME_BG_MID)
        stylesheet = stylesheet.replace('@THEME_TEXT_DARK', theme_dark.THEME_TEXT_DARK)
        stylesheet = stylesheet.replace('@THEME_BG_EXTRALIGHT', theme_dark.THEME_BG_EXTRALIGHT)
        stylesheet = stylesheet.replace('@THEME_TEXT_LIGHT', theme_dark.THEME_TEXT_LIGHT)
        stylesheet = stylesheet.replace('@THEME_TEXT_ACCENT', theme_dark.THEME_TEXT_ACCENT)
        stylesheet = stylesheet.replace('@THEME_BG_SELECTED', theme_dark.THEME_BG_SELECTED)
        stylesheet = stylesheet.replace('@THEME_MENU_SELECTED', theme_dark.THEME_MENU_SELECTED)
        stylesheet = stylesheet.replace('@THEME_MAIN_BUTTON_DARK', theme_dark.THEME_MAIN_BUTTON_DARK)
        stylesheet = stylesheet.replace('@THEME_MAIN_BUTTON_MID', theme_dark.THEME_MAIN_BUTTON_MID)
        stylesheet = stylesheet.replace('@THEME_MAIN_BUTTON_LIGHT', theme_dark.THEME_MAIN_BUTTON_LIGHT)
    else:
        raise NotImplementedError
    return stylesheet

def get_theme_colors(theme='dark'):
    """ Returns the colors of the given theme.

    :return dictionary: theme colors
    """
    if theme == 'dark':
        colors = {"THEME_BG_DARK": theme_dark.THEME_BG_DARK,
                  "THEME_BG_LIGHT": theme_dark.THEME_BG_LIGHT,
                  "THEME_BG_MID": theme_dark.THEME_BG_MID,
                  "THEME_TEXT_DARK": theme_dark.THEME_TEXT_DARK,
                  "THEME_BG_EXTRALIGHT": theme_dark.THEME_BG_EXTRALIGHT,
                  "THEME_TEXT_LIGHT": theme_dark.THEME_TEXT_LIGHT,
                  "THEME_TEXT_ACCENT": theme_dark.THEME_TEXT_ACCENT,
                  "THEME_BG_SELECTED": theme_dark.THEME_BG_SELECTED,
                  "THEME_MENU_SELECTED": theme_dark.THEME_MENU_SELECTED,
                  "THEME_MAIN_BUTTON_DARK": theme_dark.THEME_MAIN_BUTTON_DARK,
                  "THEME_MAIN_BUTTON_MID": theme_dark.THEME_MAIN_BUTTON_MID,
                  "THEME_MAIN_BUTTON_LIGHT": theme_dark.THEME_MAIN_BUTTON_LIGHT
                  }
    else:
        raise NotImplementedError
    return colors

def warning_dialog(title, message):
    """ This function shows a warning dialog. """


    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Warning)
    msg.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), '../images/medusa_favicon.png')))
    msg.setText(message)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    return msg.exec_()