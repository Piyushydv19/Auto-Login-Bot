"""
AutoLogin Platform — Flask + Selenium backend
Intelligent multi-site login manager
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import json
import os
import time
import random

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
CORS(app)

CREDENTIALS_FILE = "credentials.json"
SCREENSHOTS_DIR = "screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# key: "{site_id}:{profile_name}" → status string
login_status: dict[str, str] = {}


# ══════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════

def load_data() -> list[dict]:
    """Return list of site objects from credentials.json."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data: list[dict]) -> None:
    """Persist site list to credentials.json."""
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def find_site(data: list[dict], site_id: str):
    return next((s for s in data if s["id"] == site_id), None)


def build_site_id(name: str) -> str:
    return name.lower().strip().replace(" ", "_")


def next_profile_name(site: dict) -> str:
    count = len(site.get("profiles", [])) + 1
    return f"Profile {count}"


def profile_key(site_id: str, profile_name: str) -> str:
    return f"{site_id}:{profile_name}"


# ══════════════════════════════════════════════
# SELENIUM DRIVER
# ══════════════════════════════════════════════

def build_driver() -> webdriver.Chrome:
    opts = Options()

    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
})
"""
        }
    )

    return driver


# ══════════════════════════════════════════════
# HUMAN-LIKE HELPERS
# ══════════════════════════════════════════════

def human_type(el, text: str) -> None:
    """Fast type with small delays."""

    el.clear()
    time.sleep(0.1)

    if len(text) > 4:

        el._parent.execute_script(
            "arguments[0].value = arguments[1];",
            el,
            text[:-3]
        )

        el._parent.execute_script(
            """
arguments[0].dispatchEvent(
    new Event('input', { bubbles: true })
);
""",
            el
        )

        for ch in text[-3:]:
            el.send_keys(ch)
            time.sleep(random.uniform(0.04, 0.09))

    else:
        for ch in text:
            el.send_keys(ch)
            time.sleep(random.uniform(0.04, 0.09))


def human_click(driver, el) -> None:
    ActionChains(driver).move_to_element(el).pause(0.15).click().perform()


# ══════════════════════════════════════════════
# AUTO-DETECT LOGIN FIELDS
# ══════════════════════════════════════════════

USERNAME_SELECTORS = [
    "input[type='email']",
    "input[name='email']",
    "input[id='email']",
    "input[name='username']",
    "input[id='username']",
    "input[autocomplete='username']",
    "input[autocomplete='email']",
    "input[type='text']",
]

PASSWORD_SELECTORS = [
    "input[type='password']",
    "input[name='password']",
    "input[id='password']",
]

SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button[id*='login']",
    "button[id*='signin']",
    "button[class*='login']",
    "button[class*='signin']",
    "button",
]


def find_visible(driver, selectors: list[str]):
    """Return first visible interactable element."""

    for sel in selectors:

        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)

            for el in els:
                if el.is_displayed() and el.is_enabled():
                    return el

        except Exception:
            continue

    return None


def auto_detect_and_login(driver, site: dict, profile: dict) -> None:

    driver.get(site["url"])

    time.sleep(random.uniform(2.5, 3.5))

    user_el = find_visible(driver, USERNAME_SELECTORS)

    if not user_el:
        raise RuntimeError("Could not detect username/email field")

    human_click(driver, user_el)
    human_type(user_el, profile["username"])

    time.sleep(random.uniform(0.3, 0.6))

    pass_el = find_visible(driver, PASSWORD_SELECTORS)

    if not pass_el:
        raise RuntimeError("Could not detect password field")

    human_click(driver, pass_el)
    human_type(pass_el, profile["password"])

    time.sleep(random.uniform(0.3, 0.6))

    submit_el = find_visible(driver, SUBMIT_SELECTORS)

    if not submit_el:
        raise RuntimeError("Could not detect submit button")

    human_click(driver, submit_el)

    print(f"[{site['name']}][{profile['profile_name']}] Login submitted.")


# ══════════════════════════════════════════════
# SITE-SPECIFIC OVERRIDES
# ══════════════════════════════════════════════

def login_instagram(driver, profile: dict) -> None:

    wait = WebDriverWait(driver, 40)

    driver.get("https://www.instagram.com/accounts/login/")

    time.sleep(3)

    user_el = wait.until(
        EC.element_to_be_clickable((By.NAME, "username"))
    )

    pass_el = wait.until(
        EC.element_to_be_clickable((By.NAME, "password"))
    )

    human_click(driver, user_el)
    human_type(user_el, profile["username"])

    time.sleep(1)

    human_click(driver, pass_el)
    human_type(pass_el, profile["password"])

    time.sleep(2)

    btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
    )

    human_click(driver, btn)

    print(f"[Instagram][{profile['profile_name']}] Login submitted.")


def login_linkedin(driver, profile: dict) -> None:

    wait = WebDriverWait(driver, 40)

    driver.get("https://www.linkedin.com/login")

    time.sleep(3)

    user_el = wait.until(
        EC.element_to_be_clickable((By.ID, "username"))
    )

    pass_el = wait.until(
        EC.element_to_be_clickable((By.ID, "password"))
    )

    human_click(driver, user_el)
    human_type(user_el, profile["username"])

    time.sleep(1)

    human_click(driver, pass_el)
    human_type(pass_el, profile["password"])

    time.sleep(2)

    btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
    )

    human_click(driver, btn)

    print(f"[LinkedIn][{profile['profile_name']}] Login submitted.")


# ══════════════════════════════════════════════
# MAIN LOGIN WORKER
# ══════════════════════════════════════════════

def perform_login(site: dict, profile: dict) -> None:

    key = profile_key(site["id"], profile["profile_name"])

    login_status[key] = "Running"

    driver = None

    try:

        driver = build_driver()

        sid = site["id"]

        if sid == "instagram":
            login_instagram(driver, profile)

        elif sid == "linkedin":
            login_linkedin(driver, profile)

        else:
            auto_detect_and_login(driver, site, profile)

        if profile.get("otp_required"):

            login_status[key] = "Waiting OTP"

            print(
                f"[{site['name']}][{profile['profile_name']}] Waiting for OTP..."
            )

            time.sleep(30)

        ss_path = os.path.join(
            SCREENSHOTS_DIR,
            f"{site['id']}_{profile['profile_name'].replace(' ', '_')}.png"
        )

        try:
            driver.save_screenshot(ss_path)

        except Exception:
            pass

        login_status[key] = "Success"

        print(f"[{site['name']}][{profile['profile_name']}] Done.")

    except Exception as e:

        login_status[key] = f"Failed: {e}"

        print(
            f"[{site['name']}][{profile['profile_name']}] ERROR: {e}"
        )

    finally:
        pass


# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def home():

    with open("index.html", encoding="utf-8") as f:
        return f.read()


@app.route("/api/sites", methods=["GET"])
def get_sites():
    return jsonify(load_data())


@app.route("/api/sites", methods=["POST"])
def add_account():

    body = request.get_json(force=True)

    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not all([name, url, username, password]):

        return jsonify({
            "success": False,
            "error": "Missing fields"
        }), 400

    data = load_data()

    site_id = build_site_id(name)

    site = find_site(data, site_id)

    profile = {
        "profile_name": "",
        "username": username,
        "password": password,
    }

    if site:

        profile["profile_name"] = next_profile_name(site)

        site["profiles"].append(profile)

    else:

        profile["profile_name"] = "Profile 1"

        site = {
            "id": site_id,
            "name": name,
            "url": url,
            "profiles": [profile],
        }

        data.append(site)

    save_data(data)

    return jsonify({
        "success": True,
        "site": site
    })


@app.route(
    "/api/sites/<site_id>/profiles/<path:profile_name>",
    methods=["DELETE"]
)
def delete_profile(site_id: str, profile_name: str):

    data = load_data()

    site = find_site(data, site_id)

    if not site:

        return jsonify({
            "success": False,
            "error": "Site not found"
        }), 404

    site["profiles"] = [
        p for p in site["profiles"]
        if p["profile_name"] != profile_name
    ]

    for i, p in enumerate(site["profiles"], 1):
        p["profile_name"] = f"Profile {i}"

    if not site["profiles"]:
        data = [s for s in data if s["id"] != site_id]

    save_data(data)

    return jsonify({"success": True})


@app.route("/api/sites/<site_id>", methods=["DELETE"])
def delete_site(site_id: str):

    data = load_data()

    data = [s for s in data if s["id"] != site_id]

    save_data(data)

    return jsonify({"success": True})


@app.route("/api/login/<site_id>/<path:profile_name>", methods=["POST"])
def login_profile(site_id: str, profile_name: str):

    data = load_data()

    site = find_site(data, site_id)

    if not site:

        return jsonify({
            "success": False,
            "error": "Site not found"
        }), 404

    profile = next(
        (
            p for p in site["profiles"]
            if p["profile_name"] == profile_name
        ),
        None
    )

    if not profile:

        return jsonify({
            "success": False,
            "error": "Profile not found"
        }), 404

    key = profile_key(site_id, profile_name)

    if login_status.get(key) == "Running":

        return jsonify({
            "success": False,
            "error": "Already running"
        }), 409

    threading.Thread(
        target=perform_login,
        args=(site, profile),
        daemon=True
    ).start()

    return jsonify({
        "success": True,
        "message": f"Logging into {site['name']} / {profile_name}"
    })


@app.route("/api/login/<site_id>", methods=["POST"])
def login_all_profiles(site_id: str):

    data = load_data()

    site = find_site(data, site_id)

    if not site:

        return jsonify({
            "success": False,
            "error": "Site not found"
        }), 404

    for profile in site["profiles"]:

        key = profile_key(site_id, profile["profile_name"])

        if login_status.get(key) != "Running":

            threading.Thread(
                target=perform_login,
                args=(site, profile),
                daemon=True
            ).start()

    return jsonify({
        "success": True,
        "message": f"Logging into all profiles for {site['name']}"
    })


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(login_status)


# ══════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════

if __name__ == "__main__":

    print("🚀 AutoLogin Platform → http://127.0.0.1:5000")

    app.run(
        debug=False,
        host="0.0.0.0",
        port=5000
    )