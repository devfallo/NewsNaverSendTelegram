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
import json

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
    regDt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Add current date and time
    print(f"[{regDt}] 뉴스 스크래핑 및 전송 작업을 시작합니다.")

    url = "https://news.naver.com/main/ranking/popularDay.naver"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url)

            await click_until_disappear(page, "button_rankingnews_more")
            print("버튼 클릭 작업이 완료되었습니다. 다음 작업을 수행합니다.")

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            all_components = soup.find('div', class_='_popularRanking')

            press_boxes = all_components.find_all('div', class_='rankingnews_box')
            print(f"총 {len(press_boxes)}개의 언론사 랭킹 박스를 찾았습니다.")
            
            message_parts = []
            news_data = []  # Ensure news_data is initialized before use

            if not press_boxes:
                print("오류: 개별 언론사 랭킹 박스(class='rankingnews_box')를 찾을 수 없습니다.")
                return

            current_time_str = escape_markdown_v2(datetime.now().strftime('%Y년 %m월 %d일 %H시 기준'))
            message_parts = [f"*{current_time_str} 언론사별 뉴스 랭킹*"]

            for box in press_boxes:
                press_head = box.find('a', class_='rankingnews_box_head')
                # print("press_head : ", press_head)
                if not press_head:
                    continue

                press_name_tag = press_head.find('strong', class_='rankingnews_name')
                # print("press_name_tag : ", press_name_tag)
                if not press_name_tag:
                    continue

                press_name = escape_markdown_v2(press_name_tag.text.strip())
                message_parts.append(f"\n📰 *{press_name}*")

                news_list = box.find('ul', class_='rankingnews_list')
                if not news_list:
                    continue

                articles = []
                for article in news_list.find_all('li'):
                    title_tag = article.find('a', class_='list_title')
                    if title_tag and title_tag.has_attr('href'):
                        title = title_tag.text.strip()
                        link = title_tag['href']
                        img_tag = article.find('img')  # img 태그 추출
                        img_src = img_tag['src'] if img_tag and img_tag.has_attr('src') else None  # img src 추출
                        time_tag = article.find('span', class_='list_time')  # span 태그에서 class가 list_time인 요소 추출
                        time = time_tag.text.strip() if time_tag else None  # time 값 추출
                        if not link.startswith('http'):
                            link = "https://news.naver.com" + link
                        articles.append({"title": title, "link": link, "img_src": img_src, "time": time})

                # 뉴스 데이터를 news_data 리스트에 추가
                
                new_entry = {"press_name": press_name, "articles": articles, "regDt": regDt}  # Add regDt to the same level as press_name
                news_data.append(new_entry)
            
            print("모든 언론사 뉴스 랭킹 처리가 완료되었습니다. 다음 작업을 수행합니다.")

            # 뉴스 데이터를 JSON 파일로 저장
            if news_data:  # Ensure there is data to save
                try:
                    with open('news_data.json', 'r', encoding='utf-8') as json_file:
                        existing_data = json.load(json_file)
                except (FileNotFoundError, json.JSONDecodeError):
                    existing_data = []

                today_str = datetime.now().strftime('%Y-%m-%d')
                for item in existing_data:
                    regDt = item.get('regDt', '')
                    if not regDt.startswith(today_str):
                        item['articles'] = []

                for new_entry in news_data:
                    press_name = new_entry["press_name"]
                    articles = new_entry["articles"]

                    # Find existing press_name entry
                    existing_entry = next((item for item in existing_data if item["press_name"] == press_name), None)

                    if existing_entry:
                        existing_entry['regDt'] = regDt
                        for article in articles:
                            if not any(existing_article["title"] == article["title"] or existing_article["link"] == article["link"] for existing_article in existing_entry["articles"]):
                                existing_entry["articles"].insert(0, article)  # Add new articles at the beginning
                    else:
                        new_entry['regDt'] = regDt
                        existing_data.append(new_entry)

                with open('news_data.json', 'w', encoding='utf-8') as json_file:
                    json.dump(existing_data, json_file, ensure_ascii=False, indent=4)
                print("뉴스 데이터를 news_data.json 파일로 저장했습니다.")
            else:
                print("저장할 뉴스 데이터가 없습니다.")

            final_message = "\n".join(message_parts)

            if len(final_message.strip()) <= len(message_parts[0]):
                print("전송할 뉴스 내용이 없습니다. 파싱 결과를 확인해주세요.")
                return
            print("final_message 길이:", len(final_message))
            if len(final_message) > 4096:
                final_message = final_message[:4090] + "..."
                print("경고: 메시지가 너무 길어 일부를 잘랐습니다.")
            # print("최종 메시지:\n", final_message)

            # bot = Bot(token=TELEGRAM_BOT_TOKEN)
            # await bot.send_message(
            #     chat_id=TELEGRAM_CHAT_ID,
            #     text=final_message,
            #     parse_mode=ParseMode.MARKDOWN_V2,
            #     disable_web_page_preview=True
            # )
            # print("메시지를 성공적으로 전송했습니다.")
    except requests.exceptions.RequestException as e:
        print(f"네트워크 오류가 발생했습니다: {e}")
    except telegram.error.TelegramError as e:
        print(f"텔레그램 API 오류가 발생했습니다: {e}")
    except Exception as e:
        print(f"스크립트 실행 중 알 수 없는 오류가 발생했습니다: {e}")
    finally:
        try:
            await browser.close()
        except NameError:
            print("'browser' 객체가 정의되지 않았습니다. 브라우저를 닫을 수 없습니다.")


if __name__ == "__main__":
    print("스크립트를 테스트 모드로 1회 실행합니다.")
    asyncio.run(scrape_and_send_news())
