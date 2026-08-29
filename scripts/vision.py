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
    return i-1, labels, stats, centroids

board, hsvBoard = get_board()
mask = get_mask(hsvBoard)
pieces = get_pieces(mask)

def find_arrowheads(pieces):
    numPieces, labels, _, _ = pieces

    distTrans = cv2.distanceTransform(mask, distanceType=cv2.DIST_L2, maskSize=5)

    arrowheads = []

    for i in range(1, numPieces + 1):
        componentDist = np.where(labels == i, distTrans, 0.0)
        maxVal = np.max(componentDist)
        matchingY, matchingX = np.where(componentDist == maxVal)

        peakY = matchingY[0]
        peakX = matchingX[0]

        arrowheads.append((peakX, peakY))

    return arrowheads

print(f"Detected {len(find_arrowheads(pieces))} arrowheads.")