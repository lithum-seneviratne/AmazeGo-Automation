from pathlib import Path
import base64, numpy as np, cv2
import time
import webdriver
import sys

HOME_DIR = Path(__file__).resolve().parent.parent

DIRECTIONS = {
    'Up':    (0, -1),
    'Down':  (0, 1),
    'Left':  (-1, 0),
    'Right': (1, 0)
    }

OPPOSITES = {'Up': 'Down', 'Down': 'Up', 'Left': 'Right', 'Right': 'Left'}

def get_screenshot():
    png = base64.b64decode(webdriver.get_screenshot())
    frame = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "Level17.png"), frame)
    return frame

def get_board_shape(frame):
    colPxAvg = frame.mean(axis=0)
    rowPxAvg = frame.mean(axis=1)

    target = np.array([69.0, 29.0, 241.0])

    isColMatch = np.all(np.abs(colPxAvg - target) == 0, axis=1)
    isRowMatch = np.all(np.abs(rowPxAvg - target) == 0, axis=1)

    colMax, colMin = (np.where(~isColMatch)[0]).max(), (np.where(~isColMatch)[0]).min() 
    rowMax, rowMin = (np.where(~isRowMatch)[0]).max(), (np.where(~isRowMatch)[0]).min() 

    return rowMin, rowMax, colMin, colMax

def get_board(frame):
    croppedFrame = frame[500:2200, 0:1206]
    hsv = cv2.cvtColor(croppedFrame, cv2.COLOR_BGR2HSV)
    heightMin, heightMax, widthMin, widthMax = get_board_shape(hsv)
    return croppedFrame[heightMin:heightMax, widthMin:widthMax+1], hsv[heightMin:heightMax, widthMin:widthMax+1], widthMin, heightMin 

def get_mask(hsvBoard):
    lower = np.array([0, 0, 202], dtype=np.uint8)
    upper = np.array([180, 255, 255], dtype=np.uint8)
    mask = cv2.bitwise_not(cv2.inRange(hsvBoard, lower, upper))
    return mask

def get_pieces(mask):
    i, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8, ltype=cv2.CV_32S)
    return i-1, labels, stats, centroids

def walk(mask, x, y, dx, dy, checkBlocked=False):
    steps = 0
    h, w = mask.shape
    currentX, currentY = x + dx, y + dy
    blocked = False

    if checkBlocked:
        while 0 <= currentX < w and 0 <= currentY < h and mask[currentY, currentX] == 0:
                steps += 1
                currentX += dx
                currentY += dy
                if not (0 <= currentX < w and 0 <= currentY < h):
                    blocked = True

        return steps, blocked
    else:    
        while 0 <= currentX < w and 0 <= currentY < h and mask[currentY, currentX] > 0:
            steps += 1
            currentX += dx
            currentY += dy
        
        return steps, blocked


def find_arrowheads(mask, pieces):
    numPieces, labels, _, _ = pieces

    distTrans = cv2.distanceTransform(mask, distanceType=cv2.DIST_L2, maskSize=5)

    debugBoard = board.copy()
    arrowheads = []

    for i in range(1, numPieces + 1):
        componentDist = np.where(labels == i, distTrans, 0.0)
        maxVal = np.max(componentDist)
        matchingY, matchingX = np.where(componentDist == maxVal)

        peakY = matchingY[0]
        peakX = matchingX[0]

        runLengths = {}
        for name, (dx, dy) in DIRECTIONS.items():
            runLengths[name] = walk(mask, peakX, peakY, dx, dy)[0]

        tailDir = max(runLengths, key=runLengths.get)
        arrowDir = OPPOSITES[tailDir]

        arrowheads.append([peakX, peakY, arrowDir, runLengths[arrowDir]])

        cv2.circle(debugBoard, (peakX, peakY), radius=3, color=(0, 0, 255), thickness=-1)
        cv2.putText(debugBoard, f"{i}", (peakX + 5, peakY + 5), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "arrow_debug.png"), debugBoard)
    return arrowheads

while True:
    time.sleep(1)
    frame = get_screenshot()
    board, hsvBoard, widthMin, heightMin = get_board(frame)
    mask = get_mask(hsvBoard)   
    pieces = get_pieces(mask)
    heads = find_arrowheads(mask, pieces)

    debugFrame = frame.copy()
    for i, arrow in enumerate(heads):
        x, y, direction, headLength = arrow
        dx, dy = DIRECTIONS[direction]

        tipX = x + (dx * headLength)
        tipY = y + (dy * headLength)

        if walk(mask, tipX, tipY, dx, dy, checkBlocked=True)[1]:
            origY = y + heightMin + 500
            origX = x + widthMin
            cv2.circle(debugFrame, (origX, origY), radius=3, color=(0, 255, 0), thickness=-1)
            print(i)
            webdriver.tap(origX, origY)

    cv2.imwrite(str(Path(HOME_DIR) / "images" / "debug" / "frame_debug.png"), debugFrame)
