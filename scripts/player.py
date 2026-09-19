from pathlib import Path
import solver, webdriver
import cv2, time, base64, numpy as np

HOME_DIR = Path(__file__).resolve().parent.parent

def get_screenshot():
    png = base64.b64decode(webdriver.get_screenshot())
    frame = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "currentFrame.png"), frame)
    return frame

pic = get_screenshot()

time.sleep(0.5)

webdriver.tap(138, 2210)

time.sleep(0.5)

sel = get_screenshot()

picHSV = cv2.cvtColor(pic, cv2.COLOR_BGR2HSV)

rowMin, rowMax, colMin, colMax = solver.get_board_shape(picHSV)
picCropped = pic[rowMin:rowMax+1, colMin:colMax+1]
selCropped = sel[rowMin:rowMax+1, colMin:colMax+1]

cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "picCropped.png"), picCropped)
cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "selCropped.png"), selCropped)

targets, out = solver.get_targets(picCropped, selCropped)
cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "Out.png"), out)
print(len(targets))

for i, target in enumerate(targets):
    x, y = target
    print(f"Tapping Region {i+1} at: {x}, {y}")
    webdriver.tap(x, y)
    time.sleep(0.5)
    
