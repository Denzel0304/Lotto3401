import os
import re
import requests
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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


def main():
    lotto = get_winning_numbers()
    if not lotto:
        print("❌ 당첨번호 획득 실패. 종료.")
        return

    win_nums = lotto["numbers"]
    round_num = lotto["round"]

    # is_checked = FALSE인 row 전부 조회
    response = supabase.table("zlotto").select("*").eq("is_checked", False).execute()
    rows = response.data

    if not rows:
        print("ℹ️ 확인할 번호 없음.")
        return

    print(f"📋 미확인 항목: {len(rows)}개")

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

        print(f"✅ {row['id']} | 내 번호: {my_nums} | 맞은 수: {match_cnt} | 결과: {result_label}")

    print(f"🎉 총 {len(rows)}개 처리 완료")


if __name__ == "__main__":
    main()
