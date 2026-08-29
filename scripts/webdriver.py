from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

opts = XCUITestOptions()
opts.set_capability("platformName", "iOS")
opts.set_capability("automationName", "XCUITest")
opts.set_capability("udid", "00008140-001130441A2A801C")
opts.set_capability("webDriverAgentUrl", "http://127.0.0.1:8100")
opts.set_capability("skipLogCapture", True)
opts.set_capability("appium:plugins", ["ocr"])
opts.set_capability("appium:settings[mjpegServerFramerate]", 60)
opts.set_capability("appium:settings[mjpegServerScreenshotQuality]", 100)
opts.set_capability("appium:settings[mjpegScalingFactor]", 50)
opts.set_capability("appium:newCommandTimeout", 0)


_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = webdriver.Remote("http://127.0.0.1:4723", options=opts)
    return _driver

def get_screenshot():
    return get_driver().get_screenshot_as_base64()

def tap(pxX, pxY):
    x, y = to_points(pxX, pxY)
    get_driver().execute_script("mobile: tap", {"x": f"{x}", "y": f"{y}"})

def reset_board():
    def settings():
        actions = ActionChains(get_driver())
        actions.w3c_actions = ActionBuilder(get_driver(), mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.w3c_actions.pointer_action.move_to_location(368, 186)
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(0.1)
        actions.w3c_actions.pointer_action.release()
        actions.perform()
    def restart():
        actions = ActionChains(get_driver())
        actions.w3c_actions = ActionBuilder(get_driver(), mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.w3c_actions.pointer_action.move_to_location(280, 558)
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(0.1)
        actions.w3c_actions.pointer_action.release()
        actions.perform()
    settings()
    restart()

def to_points(x, y):
    pointX = x / 3
    pointY = y / 3
    return (pointX, pointY)

def dragFromToWithVelocity(FpxX, FpxY, TpxX, TpxY):
    fromX, fromY = to_points(FpxX, FpxY)
    toX, toY = to_points(TpxX, TpxY)
    get_driver().execute_script("mobile: dragFromToWithVelocity", {"pressDuration": "0.1", "holdDuration": "0.05", "velocity": "600", "fromX": f"{fromX}", "fromY": f"{fromY}", "toX": f"{toX}", "toY": f"{toY}"})

def get_source():
    return get_driver().execute_script("mobile: source", {"format": "description"})

def get_active_app_info():
    return get_driver().execute_script("mobile: activeAppInfo")

def set_active_app(bundleId):
    return get_driver().execute_script("mobile: activeApp", {"bundleId": f"{bundleId}"})

def terminate_app(bundleId):
    return get_driver().execute_script("mobile: terminateApp", {"bundleId": f"{bundleId}"})

def launch_app(bundleId):
    return get_driver().execute_script("mobile: launchApp", {"bundleId": f"{bundleId}"})

def settings():
    return get_driver().get_settings()