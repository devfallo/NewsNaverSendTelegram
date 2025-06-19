import requests
from bs4 import BeautifulSoup
import telegram
from datetime import datetime
import asyncio
# python-telegram-bot v20+에 맞는 import 구문으로 수정
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import os
from playwright.async_api import async_playwright

# --- 텔레그램 봇 설정 ---
# ※ 보안을 위해 봇 토큰과 채팅 ID는 환경 변수로 관리하는 것을 강력히 권장합니다.
# 로컬에서 테스트할 경우, 아래 문자열에 직접 값을 입력해도 됩니다.
# 예: TELEGRAM_BOT_TOKEN = "12345:ABCDE..."
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "")
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', "")

def escape_markdown_v2(text):
    """Telegram MarkdownV2 파싱을 위한 특수 문자 이스케이프 처리"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(['\\' + char if char in escape_chars else char for char in str(text)])

async def send_message(final_message):
    """텔레그램으로 메시지를 전송하는 비동기 함수"""
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=final_message,
        parse_mode='MarkdownV2',
        disable_web_page_preview=True
    )

async def click_until_disappear(page, button_class):
    """버튼이 사라질 때까지 3초마다 체크하며 클릭하는 함수"""
    while True:
        try:
            button = page.locator(f".{button_class}")
            if not await button.is_visible():
                break
            await button.click()
            await asyncio.sleep(3)  # 3초 대기
        except Exception as e:
            print(f"버튼 '{button_class}'이 더 이상 보이지 않거나 오류가 발생했습니다: {e}")
            break

async def scrape_and_send_news():
    """
    Naver 뉴스 언론사별 랭킹을 스크랩하여 제목과 링크를 텔레그램으로 전송합니다.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 뉴스 스크래핑 및 전송 작업을 시작합니다.")

    url = "https://news.naver.com/main/ranking/popularDay.naver"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url)

            await click_until_disappear(page, "button_rankingnews_more")

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            all_components = soup.find('div', class_='_popularRanking')

            press_boxes = all_components.find_all('div', class_='rankingnews_box')
            print(f"총 {len(press_boxes)}개의 언론사 랭킹 박스를 찾았습니다.")
            if not press_boxes:
                print("오류: 개별 언론사 랭킹 박스(class='rankingnews_box')를 찾을 수 없습니다.")
                return

            current_time_str = escape_markdown_v2(datetime.now().strftime('%Y년 %m월 %d일 %H시 기준'))
            message_parts = [f"*{current_time_str} 언론사별 뉴스 랭킹*"]

            for box in press_boxes[:5]:
                press_head = box.find('a', class_='rankingnews_box_head')
                if not press_head:
                    continue

                press_name_tag = press_head.find('strong', class_='rankingnews_name')
                if not press_name_tag:
                    continue

                press_name = escape_markdown_v2(press_name_tag.text.strip())
                message_parts.append(f"\n\n📰 *{press_name}*")

                news_list = box.find('ul', class_='rankingnews_list')
                if not news_list:
                    continue

                articles = news_list.find_all('li', limit=5)
                for i, article in enumerate(articles, 1):
                    title_tag = article.find('a', class_='list_title')

                    if title_tag and title_tag.has_attr('href'):
                        title = escape_markdown_v2(title_tag.text.strip())
                        link = title_tag['href']

                        if not link.startswith('http'):
                            link = "https://news.naver.com" + link

                        message_parts.append(f"{i}\\. [{title}]({link})")

            final_message = "\n".join(message_parts)

            if len(final_message.strip()) <= len(message_parts[0]):
                print("전송할 뉴스 내용이 없습니다. 파싱 결과를 확인해주세요.")
                return

            if len(final_message) > 4096:
                final_message = final_message[:4090] + "..."
                print("경고: 메시지가 너무 길어 일부를 잘랐습니다.")
            print("최종 메시지:\n", final_message)

            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=final_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            print("메시지를 성공적으로 전송했습니다.")

    except requests.exceptions.RequestException as e:
        print(f"네트워크 오류가 발생했습니다: {e}")
    except telegram.error.TelegramError as e:
        print(f"텔레그램 API 오류가 발생했습니다: {e}")
    except Exception as e:
        print(f"스크립트 실행 중 알 수 없는 오류가 발생했습니다: {e}")
    finally:
        try:
            browser.close()
        except NameError:
            print("'browser' 객체가 정의되지 않았습니다. 브라우저를 닫을 수 없습니다.")


if __name__ == "__main__":
    print("스크립트를 테스트 모드로 1회 실행합니다.")
    asyncio.run(scrape_and_send_news())
