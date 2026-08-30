from pathlib import Path
import solver, webdriver
import cv2, time

def state_check():
    frame = solver.get_screenshot()
    THRESHOLD = 0.99

    template_paths = [
        Path(solver.HOME_DIR) / "images" / "templates" / "continue_button_template.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "restart_button_template.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "home_screen_template.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "next_button_template.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "game_screen_template.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "next_button_template2.png",
        Path(solver.HOME_DIR) / "images" / "templates" / "next_button_template3.png",
    ]

    detected_template = None
    max_confidence = 0.0

    for t_path in template_paths:
        template = cv2.imread(str(t_path), cv2.IMREAD_COLOR_BGR)
        if template is None:
            continue

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        if max_val >= THRESHOLD and max_val > max_confidence:
            max_confidence = max_val
            detected_template = t_path.name

    if detected_template:
        print(f"Found {detected_template} with confidence {max_confidence:.2f}")
        return True, {detected_template}
    else:
        print("No matching templates found on screen.")
        return False, None

while True:
    detected, template = state_check()
    if detected:
        match str(template):
            case "{'continue_button_template.png'}":
                webdriver.tap(603, 2100)
                time.sleep(5)
                continue
            case "{'restart_button_template.png'}":
                webdriver.tap(603, 1600)
                time.sleep(5)
                continue
            case "{'home_screen_template.png'}":
                webdriver.tap(603, 1950)
                time.sleep(5)
                continue
            case "{'next_button_template.png'}":
                webdriver.tap(603, 2000)
                time.sleep(5)
                continue
            case "{'next_button_template2.png'}":
                webdriver.tap(603, 2000)
                time.sleep(5)
                continue
            case "{'next_button_template3.png'}":
                webdriver.tap(603, 2000)
                time.sleep(5)
                continue
        if str(template) == "{'game_screen_template.png'}":
            solver.main()
            time.sleep(10)
            continue
    else:
        continue