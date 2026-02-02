#!/usr/bin/env python3
import re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright, Page
from login import login

# .env loading is handled by login module import


def get_balance(page: Page) -> dict:
    """
    마이페이지에서 예치금 잔액과 구매가능 금액을 조회합니다.
    """
    print("⏳ Navigating to My Page...")
    page.goto("https://www.dhlottery.co.kr/mypage/home", timeout=30000)
    
    # Check if redirected to login
    if "/login" in page.url:
        print("⚠️ Redirection to login page detected. Attempting to log in again...")
        login(page)
        page.goto("https://www.dhlottery.co.kr/mypage/home", timeout=30000)
    
    print("⏳ Waiting for balance elements...")
    # Try multiple possible selectors for the balance
    # #navTotalAmt: header balance (preferred)
    # #totalAmt: old selector
    # .pntDpstAmt: specific deposit amount class
    try:
        # Wait for any of the common indicators
        page.wait_for_selector("#navTotalAmt, #totalAmt, .pntDpstAmt, #divCrntEntrsAmt", timeout=20000)
    except Exception as e:
        print(f"⚠️ Balance selectors not found immediately ({e}). Current page: {page.url}")
        # diagnostic: if we see login button, we are not logged in
        if page.get_by_role("link", name="로그인").is_visible():
            raise Exception("❌ Not logged in. Cannot retrieve balance.")

    # 1. Get deposit balance (예치금 잔액)
    deposit_selectors = ["#navTotalAmt", "#totalAmt", ".pntDpstAmt", ".totalAmt"]
    deposit_text = "0"
    for selector in deposit_selectors:
        el = page.locator(selector).first
        if el.is_visible():
            deposit_text = el.inner_text().strip()
            print(f"✅ Found deposit balance via {selector}")
            break
    
    # 2. Get available amount (구매가능)
    available_selectors = ["#divCrntEntrsAmt", "#tooltipTotalAmt", ".pntDpstAmt"]
    available_text = "0"
    for selector in available_selectors:
        el = page.locator(selector).first
        if el.is_visible():
            available_text = el.inner_text().strip()
            print(f"✅ Found available amount via {selector}")
            break
    
    # Parse amounts (remove non-digits)
    deposit_balance = int(re.sub(r'[^0-9]', '', deposit_text) or "0")
    available_amount = int(re.sub(r'[^0-9]', '', available_text) or "0")
    
    return {
        'deposit_balance': deposit_balance,
        'available_amount': available_amount
    }


def run(playwright: Playwright) -> dict:
    """로그인 후 잔액 정보를 조회합니다."""
    # Create browser, context, and page
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    try:
        # Perform login
        login(page)
        
        # Get balance information
        balance_info = get_balance(page)
        
        # Print results in a clean format
        print(f"💰 예치금 잔액: {balance_info['deposit_balance']:,}원")
        print(f"🛒 구매가능: {balance_info['available_amount']:,}원")
        
        return balance_info
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        # Cleanup
        context.close()
        browser.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
