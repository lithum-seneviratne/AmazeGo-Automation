from pathlib import Path
import base64, numpy as np, cv2
import time
import webdriver
import sys


HOME_DIR = Path(__file__).resolve().parent.parent

def get_screenshot():
    png = base64.b64decode(webdriver.get_screenshot())
    frame = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    return frame

# Level17Frame = get_screenshot()
# cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "Level17.png"), Level17Frame)

def get_board_shape(frame):
    colPxAvg = frame.mean(axis=0)
    rowPxAvg = frame.mean(axis=1)

    target = np.array([69.0, 29.0, 241.0])

    isColMatch = np.all(np.abs(colPxAvg - target) == 0, axis=1)
    isRowMatch = np.all(np.abs(rowPxAvg - target) == 0, axis=1)

    colMax, colMin = (np.where(~isColMatch)[0]).max(), (np.where(~isColMatch)[0]).min() 
    rowMax, rowMin = (np.where(~isRowMatch)[0]).max(), (np.where(~isRowMatch)[0]).min() 

    return rowMin, rowMax, colMin, colMax

def get_board():
    frame = cv2.imread(str(Path(HOME_DIR) / "images" / "debug" / "Level17.png"), cv2.IMREAD_COLOR_BGR)[500:2200, 0:1206]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    heightMin, heightMax, widthMin, widthMax = get_board_shape(hsv)
    return frame[heightMin:heightMax, widthMin:widthMax], hsv[heightMin:heightMax, widthMin:widthMax] 

def get_mask(hsvBoard):
    lower = np.array([0, 0, 202], dtype=np.uint8)
    upper = np.array([180, 255, 255], dtype=np.uint8)
    mask = cv2.bitwise_not(cv2.inRange(hsvBoard, lower, upper))
    return mask

def get_pieces(mask):
    i, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8, ltype=cv2.CV_32S)
    return i

board, hsvBoard = get_board()
mask = get_mask(hsvBoard)

pieces = get_pieces(mask)

print(pieces)

cv2.imshow("Board", hsvBoard)
cv2.imshow("Mask", mask)
cv2.waitKey(0)
cv2.destroyAllWindows