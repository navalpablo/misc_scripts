import pyautogui
import time

# Disable the fail-safe feature
pyautogui.FAILSAFE = False

def keep_awake(interval=60, reset_interval=600):
    try:
        screen_width, screen_height = pyautogui.size()
        reset_time = time.time() + reset_interval
        while True:
            current_time = time.time()
            
            # Reset to the center every reset_interval seconds
            if current_time >= reset_time:
                pyautogui.moveTo(screen_width / 2, screen_height / 2, duration=0.1)
                reset_time = current_time + reset_interval
                print("Mouse reset to the center of the screen.")
            
            # Move the mouse cursor slightly to simulate activity
            x, y = pyautogui.position()
            if x < screen_width - 10:
                pyautogui.moveRel(1, 0, duration=0.1)
                pyautogui.moveRel(-1, 0, duration=0.1)
            else:
                pyautogui.moveRel(-1, 0, duration=0.1)
                pyautogui.moveRel(1, 0, duration=0.1)
                
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Program terminated by user.")

if __name__ == "__main__":
    keep_awake()
