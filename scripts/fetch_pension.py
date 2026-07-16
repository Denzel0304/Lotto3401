import os
import re
import requests
from supabase import create_client, ClientOptions

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ADMIN_TOKEN  = os.environ["ADMIN_TOKEN"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(headers={"x-mac-secret": ADMIN_TOKEN})
)


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ 텔레그램 발송 완료")
        else:
            print(f"❌ 텔레그램 발송 실패: {res.text}")
    except Exception as e:
        print(f"❌ 텔레그램 오류: {e}")


def get_winning_numbers():
    """네이버에서 연금복권720+ 당첨번호 크롤링"""
    url = "https://search.naver.com/search.naver?where=nexearch&query=%EC%97%B0%EA%B8%88%EB%B3%B5%EA%B6%8C720"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text
    except Exception as e:
        print(f"❌ 크롤링 요청 실패: {e}")
        return None

    # 회차 + 날짜 추출
    date_match = re.search(r'(\d+)회차\s*[\(\（](\d{4})\.(\d{2})\.(\d{2})[\.\）\)]', html)
    if not date_match:
        date_match = re.search(r'제\s*(\d+)\s*회[^(]*\((\d{4})\.(\d{2})\.(\d{2})', html)
    if not date_match:
        print("❌ 회차/날짜 파싱 실패")
        return None

    round_num = int(date_match.group(1))
    draw_date = f"{date_match.group(2)}-{date_match.group(3)}-{date_match.group(4)}"

    # 1등 조 + 번호 추출
    # 실제 네이버 HTML 구조:
    # <td class="sub_title">1등</td>
    # <td class="sub_title">4조</td>
    # <td class="type_bold">6</td><td class="type_bold">0</td>... (6자리)
    block_match = re.search(
        r'sub_title">1등</td>\s*<td[^>]*>(\d+)조</td>((?:\s*<td[^>]*>\d+</td>){6})',
        html
    )
    if not block_match:
        print("❌ 당첨 조/번호 파싱 실패")
        print(html[:3000])
        return None

    win_group  = int(block_match.group(1))
    digits     = re.findall(r'<td[^>]*>(\d+)</td>', block_match.group(2))
    win_ticket = ''.join(digits[:6])

    if len(win_ticket) != 6:
        print(f"❌ 번호 자릿수 오류: {win_ticket}")
        return None

    print(f"✅ {round_num}회차 | 당첨: {win_group}조 {win_ticket} | 추첨일: {draw_date}")
    return {
        "round": round_num,
        "draw_date": draw_date,
        "win_group": win_group,
        "win_ticket": win_ticket
    }


def calc_result(my_group: int, my_ticket: str, win_group: int, win_ticket: str) -> str:
    """등수 계산"""
    if my_group == win_group and my_ticket == win_ticket:
        return "🏆 1등"
    if my_ticket == win_ticket:
        return "🥈 2등"  # 조만 다르고 번호 일치
    # 끝자리부터 일치 개수로 3~7등 판정
    match_digits = 0
    for i in range(5, -1, -1):
        if my_ticket[i] == win_ticket[i]:
            match_digits += 1
        else:
            break
    if match_digits == 5: return "🥉 3등"
    if match_digits == 4: return "🎖 4등"
    if match_digits == 3: return "🎗 5등"
    if match_digits == 2: return "🎀 6등"
    if match_digits == 1: return "🎁 7등"
    return "낙첨"


def build_telegram_message(pension, results):
    round_num  = pension["round"]
    draw_date  = pension["draw_date"]
    win_group  = pension["win_group"]
    win_ticket = pension["win_ticket"]

    total   = len(results)
    winners = [r for r in results if r["win_result"] != "낙첨"]
    losers  = total - len(winners)

    rank_count = {}
    for r in results:
        rank_count[r["win_result"]] = rank_count.get(r["win_result"], 0) + 1

    lines = []
    lines.append(f"🎰 <b>연금복권720+ {round_num}회차 결과</b>")
    lines.append(f"📅 추첨일: {draw_date}")
    lines.append("")
    lines.append(f"🏆 당첨번호: <b>{win_group}조 {win_ticket}</b>")
    lines.append("")
    lines.append(f"🎟 구매 복권: <b>총 {total}게임</b>")
    lines.append(f"✅ 당첨: {len(winners)}게임   ❌ 낙첨: {losers}게임")

    if rank_count:
        lines.append("")
        lines.append("📊 <b>등수별 요약</b>")
        for rank in ["🏆 1등", "🥈 2등", "🥉 3등", "🎖 4등", "🎗 5등", "🎀 6등", "🎁 7등", "낙첨"]:
            if rank in rank_count:
                lines.append(f"  {rank}: {rank_count[rank]}게임")

    lines.append("")
    lines.append("📋 <b>게임별 결과</b>")
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r['group_num']}조 {r['ticket_num']}")
        lines.append(f"      → {r['win_result']}")

    if winners:
        lines.append("")
        lines.append("🎉 <b>당첨 게임 상세</b>")
        for r in winners:
            lines.append(f"  {r['win_result']}  {r['group_num']}조 {r['ticket_num']}")
    else:
        lines.append("")
        lines.append("😢 이번 회차는 당첨이 없습니다. 다음 기회에!")

    return "\n".join(lines)


def main():
    pension = get_winning_numbers()
    if not pension:
        print("❌ 당첨번호 획득 실패. 종료.")
        send_telegram("❌ 연금복권 당첨번호 크롤링에 실패했습니다.")
        return

    win_group  = pension["win_group"]
    win_ticket = pension["win_ticket"]
    round_num  = pension["round"]

    response = supabase.table("zpension").select("*").eq("is_checked", False).eq("draw_round", round_num).execute()
    rows = response.data

    if not rows:
        print(f"ℹ️ {round_num}회차: 확인할 번호 없음. 텔레그램 알림 생략.")
        return

    print(f"📋 미확인 항목: {len(rows)}개")

    results = []

    for row in rows:
        my_group  = row["group_num"]
        my_ticket = row["ticket_num"]
        result    = calc_result(my_group, my_ticket, win_group, win_ticket)

        supabase.table("zpension").update({
            "is_checked": True,
            "win_result": result,
            "win_group":  win_group,
            "win_ticket": win_ticket
        }).eq("id", row["id"]).execute()

        results.append({
            "group_num":  my_group,
            "ticket_num": my_ticket,
            "win_result": result
        })

        print(f"✅ {row['id']} | {my_group}조 {my_ticket} | 결과: {result}")

    print(f"🎉 총 {len(rows)}개 처리 완료")

    message = build_telegram_message(pension, results)
    send_telegram(message)


if __name__ == "__main__":
    main()
