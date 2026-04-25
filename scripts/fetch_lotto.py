import os
import re
import requests
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def send_telegram(message: str):
    """텔레그램 메시지 발송"""
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
    """GAS와 동일한 방식으로 네이버에서 로또 당첨번호 크롤링"""
    url = "https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query=%EB%A1%9C%EB%98%90&ackey=hjs3285m"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text
    except Exception as e:
        print(f"❌ 크롤링 요청 실패: {e}")
        return None

    numbers = []

    # 방법 1: ball_645 클래스 패턴
    matches = re.findall(r'class="ball_645[^"]*"[^>]*>(\d+)<', html)
    numbers = [int(m) for m in matches[:6]]

    # 방법 2: winning_number div 내부
    if len(numbers) < 6:
        block = re.search(r'winning_number[^>]*>([\s\S]*?)</div>', html)
        if block:
            balls = re.findall(r'<span[^>]*ball[^>]*>(\d+)</span>', block.group(1))
            numbers = [int(b) for b in balls[:6]]

    # 방법 3: num_win 패턴
    if len(numbers) < 6:
        matches = re.findall(r'class="num_win[^"]*"[^>]*>(\d+)<', html)
        numbers = [int(m) for m in matches[:6]]

    if len(numbers) < 6:
        print(f"❌ 번호 파싱 실패. 추출된 번호: {numbers}")
        return None

    # 회차 + 날짜 추출 (GAS와 동일)
    date_match = re.search(r'(\d+)회차\s*[\(\（](\d{4})\.(\d{2})\.(\d{2})[\.\）\)]', html)
    if not date_match:
        print("❌ 회차/날짜 파싱 실패")
        return None

    round_num = int(date_match.group(1))
    draw_date = f"{date_match.group(2)}-{date_match.group(3)}-{date_match.group(4)}"

    print(f"✅ {round_num}회차 당첨번호: {numbers} | 추첨일: {draw_date}")
    return {"numbers": numbers, "round": round_num, "draw_date": draw_date}


def calc_result(my_numbers, win_numbers):
    matched = [n for n in my_numbers if n in win_numbers]
    cnt = len(matched)
    if   cnt == 6: label = "🏆 1등"
    elif cnt == 5: label = "🥈 3등"
    elif cnt == 4: label = "🥉 4등"
    elif cnt == 3: label = "🎖 5등"
    else:          label = "낙첨"
    return label, cnt


def build_telegram_message(lotto, results):
    """텔레그램 메시지 구성"""
    win_nums = lotto["numbers"]
    round_num = lotto["round"]
    draw_date = lotto["draw_date"]

    total = len(results)
    winners = [r for r in results if r["result"] != "낙첨"]
    losers = total - len(winners)

    # 등수별 카운트
    rank_count = {}
    for r in results:
        rank_count[r["result"]] = rank_count.get(r["result"], 0) + 1

    # 당첨번호 라인
    win_str = "  ".join(str(n) for n in win_nums)

    lines = []
    lines.append(f"🎱 <b>로또 {round_num}회차 결과</b>")
    lines.append(f"📅 추첨일: {draw_date}")
    lines.append("")
    lines.append(f"🔢 당첨번호:  <b>{win_str}</b>")
    lines.append("")
    lines.append(f"🎟 구매 복권: <b>총 {total}게임</b>")
    lines.append(f"✅ 당첨: {len(winners)}게임   ❌ 낙첨: {losers}게임")

    # 등수별 요약
    if rank_count:
        lines.append("")
        lines.append("📊 <b>등수별 요약</b>")
        for rank in ["🏆 1등", "🥈 3등", "🥉 4등", "🎖 5등", "낙첨"]:
            if rank in rank_count:
                lines.append(f"  {rank}: {rank_count[rank]}게임")

    # 개별 결과
    lines.append("")
    lines.append("📋 <b>게임별 결과</b>")
    for i, r in enumerate(results, 1):
        nums_str = "  ".join(str(n) for n in r["numbers"])
        lines.append(f"  {i}. [{nums_str}]")
        lines.append(f"      → {r['result']}  ({r['match_count']}개 일치)")

    # 당첨 게임 강조
    if winners:
        lines.append("")
        lines.append("🎉 <b>당첨 게임 상세</b>")
        for r in winners:
            nums_str = "  ".join(str(n) for n in r["numbers"])
            matched = [n for n in r["numbers"] if n in win_nums]
            lines.append(f"  {r['result']}  [{nums_str}]")
            lines.append(f"      일치번호: {matched}")
    else:
        lines.append("")
        lines.append("😢 이번 회차는 당첨이 없습니다. 다음 기회에!")

    return "\n".join(lines)


def main():
    lotto = get_winning_numbers()
    if not lotto:
        print("❌ 당첨번호 획득 실패. 종료.")
        send_telegram("❌ 로또 당첨번호 크롤링에 실패했습니다.")
        return

    win_nums = lotto["numbers"]
    round_num = lotto["round"]

    # is_checked = FALSE인 row 전부 조회
    response = supabase.table("zlotto").select("*").eq("is_checked", False).execute()
    rows = response.data

    if not rows:
        print("ℹ️ 확인할 번호 없음.")
        send_telegram(f"ℹ️ {round_num}회차: 이번 주에 구매한 로또가 없습니다.")
        return

    print(f"📋 미확인 항목: {len(rows)}개")

    results = []

    for row in rows:
        my_nums = [int(n) for n in row["numbers"]]
        result_label, match_cnt = calc_result(my_nums, win_nums)

        supabase.table("zlotto").update({
            "is_checked": True,
            "win_result": result_label,
            "match_count": match_cnt,
            "round": round_num,
            "win_numbers": win_nums
        }).eq("id", row["id"]).execute()

        results.append({
            "numbers": my_nums,
            "result": result_label,
            "match_count": match_cnt
        })

        print(f"✅ {row['id']} | 내 번호: {my_nums} | 맞은 수: {match_cnt} | 결과: {result_label}")

    print(f"🎉 총 {len(rows)}개 처리 완료")

    # 텔레그램 발송
    message = build_telegram_message(lotto, results)
    send_telegram(message)


if __name__ == "__main__":
    main()
