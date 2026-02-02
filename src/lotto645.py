#!/usr/bin/env python3
import json
import re
import sys
import time
from os import environ
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright
from login import login

# .env loading is handled by login module import


def parse_arguments():
    """
    커맨드라인 인자를 파싱하여 게임 설정 반환
    
    사용법:
    - Auto: ./lotto645.py 1000  (1게임)
    - Auto: ./lotto645.py 3000  (3게임)
    - Manual: ./lotto645.py 1 2 3 4 5 6  (수동 번호)
    
    Returns:
        tuple: (auto_games, manual_numbers)
    """
    if len(sys.argv) == 1:
        # No arguments - use .env configuration
        auto_games = int(environ.get('AUTO_GAMES', '0'))
        manual_numbers = json.loads(environ.get('MANUAL_NUMBERS', '[]'))
        return auto_games, manual_numbers
    
    # Parse command-line arguments
    args = sys.argv[1:]
    
    # Case 1: Single argument (auto games by amount)
    if len(args) == 1:
        amount_str = args[0].replace(',', '')  # Remove commas
        try:
            amount = int(amount_str)
            
            # Check if it's a valid auto game amount (1000-5000 in 1000 increments)
            if amount in [1000, 2000, 3000, 4000, 5000]:
                auto_games = amount // 1000
                print(f"ℹ️  Auto mode: {auto_games} game(s) (₩{amount:,})")
                return auto_games, []
            else:
                print(f"❌ Error: Invalid amount '{args[0]}'")
                print(f"Valid amounts: 1000, 2000, 3000, 4000, 5000")
                sys.exit(1)
        except ValueError:
            print(f"❌ Error: Invalid amount format '{args[0]}'")
            sys.exit(1)
    
    # Case 2: Six arguments (manual number selection)
    elif len(args) == 6:
        try:
            numbers = [int(arg) for arg in args]
            
            # Validate: all numbers must be 1-45
            if not all(1 <= n <= 45 for n in numbers):
                print(f"❌ Error: All numbers must be between 1 and 45")
                print(f"Provided: {numbers}")
                sys.exit(1)
            
            # Validate: no duplicates
            if len(numbers) != len(set(numbers)):
                print(f"❌ Error: Numbers must not contain duplicates")
                print(f"Provided: {numbers}")
                sys.exit(1)
            
            # Sort numbers for display
            sorted_numbers = sorted(numbers)
            print(f"ℹ️  Manual mode: {sorted_numbers}")
            return 0, [numbers]
            
        except ValueError:
            print(f"❌ Error: All arguments must be numbers")
            print(f"Provided: {args}")
            sys.exit(1)
    
    else:
        print(f"❌ Error: Invalid number of arguments")
        print(f"\nUsage:")
        print(f"  Auto games:   ./lotto645.py [AMOUNT]")
        print(f"                where AMOUNT is 1000, 2000, 3000, 4000, or 5000")
        print(f"  Manual game:  ./lotto645.py [N1] [N2] [N3] [N4] [N5] [N6]")
        print(f"                where each N is a number from 1 to 45 (no duplicates)")
        print(f"\nExamples:")
        print(f"  ./lotto645.py 3000          # Buy 3 auto games")
        print(f"  ./lotto645.py 1 2 3 4 5 6   # Buy 1 manual game with numbers 1,2,3,4,5,6")
        sys.exit(1)


def run(playwright: Playwright, auto_games: int, manual_numbers: list) -> None:
    """
    로또 6/45를 자동 및 수동으로 구매합니다.
    
    Args:
        playwright: Playwright 객체
        auto_games: 자동 구매 게임 수
        manual_numbers: 수동 구매 번호 리스트 (예: [[1,2,3,4,5,6], ...])
    """
    # Create browser, context, and page
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 0. Setup alert handler to automatically accept any alerts (like session timeout alerts)
    page.on("dialog", lambda dialog: dialog.accept())

    # Perform login
    try:
        login(page)

        # Navigate to the Wrapper Page (TotalGame.jsp) which handles session sync correctly
        print("🚀 Navigating to Lotto 6/45 Wrapper page...")
        game_url = "https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40"
        page.goto(game_url, timeout=30000)
        
        # Check if we were redirected to login page (session lost)
        time.sleep(1) 
        if "/login" in page.url or "method=login" in page.url:
            print("⚠️ Redirection detected. Attempting to log in again...")
            login(page)
            page.goto(game_url, timeout=30000)

        # Access the game iframe
        print("Waiting for game iframe to load...")
        try:
            page.wait_for_selector("#ifrm_tab", state="visible", timeout=20000)
            print("✅ Iframe #ifrm_tab found")
        except Exception:
            print("⚠️ Iframe #ifrm_tab not visible. Current URL:", page.url)
            
        frame = page.frame_locator("#ifrm_tab")

        # Wait for iframe content
        try:
             # Wait for a core element inside the frame
             frame.locator("#num2, #btnSelectNum").first.wait_for(state="attached", timeout=30000)
        except Exception as e:
             print(f"⚠️ Timeout waiting for iframe content ({e}). Retrying navigation...")
             page.reload(wait_until="networkidle")
             page.wait_for_selector("#ifrm_tab", state="visible", timeout=20000)
             frame.locator("#num2, #btnSelectNum").first.wait_for(state="attached", timeout=30000)

        print('✅ Navigated to Lotto 6/45 Game Frame')

        # Check if we are logged in on this frame
        try:
            user_id_val = frame.locator("input[name='USER_ID']").get_attribute("value")
            if not user_id_val:
                print("⚠️ Session not found in frame. Re-verifying...")
                # Some versions might hide logout button instead
                if not frame.get_by_text("로그아웃").first.is_visible(timeout=5000):
                    login(page)
                    page.goto(game_url, timeout=30000)
            else:
                print(f"🔑 Login ID on Game Page: {user_id_val}")
        except Exception:
            pass

        # Remove intercepting elements in iframe context
        page.evaluate("""
            () => {
                const iframe = document.querySelector('#ifrm_tab');
                if (iframe && iframe.contentDocument) {
                    const doc = iframe.contentDocument;
                    const selectors = ['.pause_layer_pop', '.pause_bg', '#popupLayerAlert'];
                    selectors.forEach(s => {
                        doc.querySelectorAll(s).forEach(el => {
                            el.style.display = 'none';
                            el.style.pointerEvents = 'none';
                        });
                    });
                }
            }
        """)

        # Wait for the game interface
        frame.locator("#num2").wait_for(state="visible", timeout=15000)
        print("✅ Game interface loaded (#num2 visible)")

        # Manual numbers
        if manual_numbers and len(manual_numbers) > 0:
            for game in manual_numbers:
                print(f"🎰 Adding manual game: {game}")
                for number in game:
                    frame.locator(f'label[for="check645num{number}"]').click(force=True)
                frame.locator("#btnSelectNum").click()

        # Automatic games
        if auto_games > 0:
            frame.locator("#num2").click() 
            frame.locator("#amoundApply").select_option(str(auto_games))
            frame.locator("#btnSelectNum").click()
            print(f'✅ Automatic game(s) added: {auto_games}')

        # Check if any games were added
        total_games = len(manual_numbers) + auto_games
        if total_games == 0:
            print('⚠️  No games to purchase!')
            return

        # Verify payment amount
        time.sleep(1)
        payment_amount_el = frame.locator("#payAmt")
        payment_text = payment_amount_el.inner_text().strip()
        payment_amount = int(re.sub(r'[^0-9]', '', payment_text))
        expected_amount = total_games * 1000
        
        if payment_amount != expected_amount:
            print(f'❌ Error: Payment mismatch (Expected {expected_amount}, Displayed {payment_amount})')
            return
        
        # Purchase
        frame.locator("#btnBuy").click()
        
        # Confirm purchase popup (Inside Frame)
        frame.locator("#popupLayerConfirm input[value='확인']").click()

        
        # Check for purchase limit alert or recommendation popup AFTER confirmation
        time.sleep(3)
        
        # 1. Check for specific limit exceeded recommendation popup
        limit_popup = frame.locator("#recommend720Plus")
        if limit_popup.is_visible():
            print("❌ Error: Weekly purchase limit exceeded (detected limit popup).")
            content = limit_popup.locator(".cont1").inner_text()
            print(f"   Message: {content.strip()}")
            return

        print(f'✅ Lotto 6/45: All {total_games} games purchased successfully!')


    finally:
        # Cleanup
        context.close()
        browser.close()


if __name__ == "__main__":
    # Parse command-line arguments or use .env configuration
    auto_games, manual_numbers = parse_arguments()
    
    with sync_playwright() as playwright:
        run(playwright, auto_games, manual_numbers)
