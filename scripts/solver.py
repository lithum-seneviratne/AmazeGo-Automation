from pathlib import Path
import base64, numpy as np, cv2
import time
import webdriver
import sys

HOME_DIR = Path(__file__).resolve().parent.parent

yOffset = 500

def get_board_shape(frame, tol=10):
    notBlack = frame.max(axis=2) > tol
    rowHas = notBlack.any(axis=1)

    padded = np.concatenate(([0], rowHas.astype(np.int8), [0]))
    edges = np.diff(padded)
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    k = np.argmax(ends - starts)
    rowMin, rowMax = starts[k], ends[k] - 1

    cols = np.where(notBlack[rowMin:rowMax+1].any(axis=0))[0]
    return rowMin, rowMax, cols.min(), cols.max()

def build_mask(picHSV):
    mask = (picHSV[:, :, 2] > 170).astype(np.uint8) * 255
    mask[:, 0] = 0
    mask[:, -1] = 0
    mask[0, :] = 0
    mask[-1, :] = 0
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

    colors = np.random.randint(0, 210, (n, 3), dtype=np.uint8)
    colors[0] = 0
    vis = colors[labels]

    centers = {}

    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        boxDist = dist[y:y+h, x:x+w]
        boxLabels = labels[y:y+h, x:x+w]
        d = np.where(boxLabels == i, boxDist, 0)
        r, c = np.unravel_index(np.argmax(d), d.shape)
        tx, ty = x + c, y + r

        centers[i] = (int(tx), int(ty) + yOffset)

    # cv2.circle(vis, (int(tx), int(ty)), 2, (0, 0, 255), -1)

    # cv2.imshow("regions", vis)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    return n, labels, stats, centers

def get_targets(pic, sel):
    diff = cv2.absdiff(pic,sel)
    changed = diff.max(axis=2) > 30

    n, labels, stats, centers = build_mask(pic)
    changedCount = np.bincount(labels.ravel(), weights=changed.ravel(), minlength=n)
    frac = changedCount / stats[:, cv2.CC_STAT_AREA]

    targets = [i for i in range(1, n) if frac[i] > 0.25]

    out = sel.copy()
    out[np.isin(labels, targets)] = (0, 0, 255)
    for i in targets:
        x, y = centers[i]
        cv2.circle(out, (x, y - yOffset), 2, (0, 255, 0), -1)

    return [centers[i] for i in targets], out


# cv2.imshow("targets", out)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
