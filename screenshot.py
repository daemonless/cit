#!/usr/bin/env python3
"""Fast screenshot using Selenium - waits for actual page load."""
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

# Config via environment variables
CHROME_BIN = os.environ.get("CHROME_BIN", "/usr/local/bin/chrome")
CHROMEDRIVER_BIN = os.environ.get("CHROMEDRIVER_BIN", "/usr/local/bin/chromedriver")
WINDOW_SIZE = os.environ.get("SCREENSHOT_SIZE", "1920,1080")

def screenshot(url, output, timeout=30):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument(f"--window-size={WINDOW_SIZE}")
    options.set_capability("acceptInsecureCerts", True)
    if CHROME_BIN:
        options.binary_location = CHROME_BIN

    service = Service(executable_path=CHROMEDRIVER_BIN)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(timeout)

    try:
        driver.get(url)
        # Wait for page to be ready
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Smart Wait: Wait for UI to stabilize (stop animating/loading)
        import time
        stable = False
        start_time = time.time()
        last_screen = None
        
        # Check for stability for up to 10 seconds
        print(f"Waiting for UI stability (max 10s)...", file=sys.stderr)
        while time.time() - start_time < 10:
            current_screen = driver.get_screenshot_as_base64()
            if last_screen and current_screen == last_screen:
                elapsed = time.time() - start_time
                print(f"UI stabilized after {elapsed:.2f}s", file=sys.stderr)
                stable = True
                break
            last_screen = current_screen
            time.sleep(0.5)
            
        if not stable:
            print("UI did not stabilize (timeout reached), taking final screenshot", file=sys.stderr)

        driver.save_screenshot(output)
        return True
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: screenshot.py URL OUTPUT [TIMEOUT]", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    output = sys.argv[2]
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    sys.exit(0 if screenshot(url, output, timeout) else 1)
