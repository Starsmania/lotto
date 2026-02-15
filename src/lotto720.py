#!/usr/bin/env python3
import json
import time
import re
from os import environ
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright
from login import login, SESSION_PATH, DEFAULT_USER_AGENT, DEFAULT_VIEWPORT, DEFAULT_HEADERS, GLOBAL_TIMEOUT

import sys
import traceback
from script_reporter import ScriptReporter

# .env loading is handled by login module import


def run(playwright: Playwright, sr: ScriptReporter) -> None:
    """
    연금복권 720+를 구매합니다.
    '모든 조'를 선택하여 임의의 번호로 5매(5,000원)를 구매합니다.
    
    Args:
        playwright: Playwright 객체
    """
    GAME_URL = "https://el.dhlottery.co.kr/game_mobile/pension720/game.jsp"
    
    # Create browser, context, and page
    HEADLESS = environ.get('HEADLESS', 'true').lower() == 'true'
    browser = playwright.chromium.launch(headless=HEADLESS, slow_mo=0 if HEADLESS else 500)

    # Load session if exists
    storage_state = SESSION_PATH if Path(SESSION_PATH).exists() else None
    context = browser.new_context(
        storage_state=storage_state,
        user_agent=DEFAULT_USER_AGENT,
        viewport=DEFAULT_VIEWPORT,
        extra_http_headers=DEFAULT_HEADERS
    )
    page = context.new_page()
    
    # Setup alert handler to automatically accept any alerts
    page.on("dialog", lambda dialog: dialog.accept())

    # Perform login only if needed
    from login import is_logged_in
    if not is_logged_in(page):
        sr.stage("LOGIN")
        login(page)
    else:
        print("Already logged in. Skipping login stage.")
    
    sr.stage("NAVIGATE")
    try:
        # Navigate to the Game Page directly
        print(f"Navigating to Lotto 720 mobile game page: {GAME_URL}")
        page.goto(GAME_URL, timeout=GLOBAL_TIMEOUT, wait_until="commit")
        print(f"Current URL: {page.url}")
        
        # Check if we were redirected to login page (session lost)
        if "/login" in page.url or "method=login" in page.url:
            print(f"Redirection detected (URL: {page.url}). Attempting to log in again...")
            login(page)
            page.goto(GAME_URL, timeout=GLOBAL_TIMEOUT, wait_until="commit")
            print(f"Current URL: {page.url}")

        # Give it a moment to load components
        time.sleep(2)
        
        # ----------------------------------------------------
        # Verify Session & Balance
        # ----------------------------------------------------
        
        # ----------------------------------------------------
        # Purchase Flow (Mobile Optimized)
        # ----------------------------------------------------
        
        # 1. Open Number Selection Options
        print("Opening selection options...")
        page.locator(".btn_gray_st1:has-text('번호 선택하기')").first.click()
        time.sleep(1)

        # 2. Click 'Automatic Number' (자동번호)
        sr.stage("PURCHASE_SELECTION")
        print("Clicking 'Automatic Number' (자동번호)...")
        page.locator("#btn_set_auto").click(force=True)
        time.sleep(0.5)
        
        # 3. Click 'Confirm Selection' (선택완료)
        print("Clicking 'Confirm Selection' (선택완료)...")
        page.locator("#btn_set_comp").click()
        time.sleep(0.5)
  
        # 4. Click 'Purchase' (구매하기)
        print("Clicking 'Purchase' (구매하기)...")
        page.locator(".btn_blue:has-text('구매하기')").first.click()
        
        # 5. Confirm Final Purchase Popup
        print("Confirming final purchase...")
        # Confirm popup often uses #popupLayerConfirm or similar
        confirm_btn = page.locator("#popupLayerConfirm").get_by_role("button", name="확인")
        if not confirm_btn.is_visible():
            confirm_btn = page.get_by_role("button", name="확인")
        confirm_btn.first.click()
        
        time.sleep(2)
        print("Lotto 720: All sets purchased successfully!")
        

    except Exception as e:
        print(f"An error occurred: {e}")
        raise # Re-raise the exception to be caught by the main block
    finally:
        # Cleanup
        context.close()
        browser.close()

if __name__ == "__main__":
    sr = ScriptReporter("Lotto 720")
    try:
        with sync_playwright() as playwright:
            run(playwright, sr)
            sr.success({"processed_count": 5}) # Fixed at 5 games as per script logic
    except Exception:
        sr.fail(traceback.format_exc())
        sys.exit(1)
