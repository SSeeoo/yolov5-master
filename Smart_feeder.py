# Smart_feeder.py
import subprocess
import pymysql
import json
import requests
import re
import time
import os
from datetime import datetime, timedelta

def get_feed_interval(user_id):
    try:
        with pymysql.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', '5611'),
                db=os.getenv('DB_NAME', 'feeder'),
                charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                sql = "SELECT interval_minutes FROM feed_interval WHERE user_id = %s"
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
    except Exception as e:
        print(f"Error getting feed interval: {e}")
        return None


# 앱의 2번째 화면 기능 구현 1) User의 시간 제한 설정
def is_time_restricted(user_id):
    try:
        with pymysql.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', '5611'),
                db=os.getenv('DB_NAME', 'feeder'),
                charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                # 사용자의 시간 제한 설정을 가져옴
                sql = "SELECT start_time, end_time FROM time_restriction WHERE user_id = %s"
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()

                if result:
                    start_time, end_time = result
                    now = datetime.now().time()  # 현재 시간
                    # 현재 시간이 사용자가 설정한 시간 제한 내에 있는지 확인
                    return start_time <= now <= end_time
                else:
                    # 설정이 없다면 기본값 사용
                    now = datetime.now()
                    return now.hour >= 21 or now.hour < 4  # 21시 ~ 4시 사이에는 배급 금지
    except pymysql.MySQLError as e:
        print("ERROR: ", e)
        return False

# 짧은 시간동안 발생하는 모터의 오작동을 방지하기 위한 함수
def can_proceed(breed):
    try:
        with pymysql.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', '5611'),
                db=os.getenv('DB_NAME', 'feeder'),
                charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                # last_detection 테이블에서 해당 품종의 마지막 감지 시간을 가져옴
                sql = "SELECT last_detected FROM last_detection WHERE breed = %s"
                cursor.execute(sql, (breed,))
                result = cursor.fetchone()

                now = datetime.now()

                if result:
                    last_detected = result[0]
                    # 마지막으로 감지된 시간과 현재 시간을 비교
                    remaining_time = timedelta(seconds=10) - (now - last_detected)
                    if remaining_time > timedelta(seconds=0):
                        remaining_seconds = int(remaining_time.total_seconds())
                        print(f"{remaining_seconds}초가 남았습니다.")
                        return False


    except pymysql.MySQLError as e:
        print("ERROR: ", e)
        return False

    return True

def log_detection(breed):
    try:
        with pymysql.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', '5611'),
                db=os.getenv('DB_NAME', 'feeder'),
                charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                now = datetime.now()

                # detection_log 테이블에 감지 이력 추가
                sql_log = "INSERT INTO detection_log (breed, time) VALUES (%s, %s)"
                cursor.execute(sql_log, (breed, now))

                # last_detection 테이블에 마지막으로 감지된 시각을 업데이트 또는 삽입
                sql_last = "INSERT INTO last_detection (breed, last_detected) VALUES (%s, %s) ON DUPLICATE KEY UPDATE last_detected = %s"
                cursor.execute(sql_last, (breed, now, now))

                conn.commit()
    except pymysql.MySQLError as e:
        print("ERROR: ", e)


def get_default_feed_amount(breed):
    try:
        # MariaDB에 연결
        with pymysql.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', '5611'),
                db=os.getenv('DB_NAME', 'feeder'),
                charset='utf8'
        ) as conn:
            # print("Database connection successful!")  # 데이터베이스에 성공적으로 연결되었다는 메시지 출력
            with conn.cursor() as cursor:
                sql = "SELECT DefaultFeedAmount FROM petbreed WHERE BreedName = %s"
                cursor.execute(sql, (breed,))
                result = cursor.fetchone()
                if result:
                    print(f"Successfully retrieved feed amount for {breed}")  # 품종에 대한 피드 양을 성공적으로 검색한 경우
                else:
                    print(f"No feed amount found for {breed}")  # 품종에 대한 피드 양을 찾지 못한 경우
                return result[0] if result else None
    except Exception as e:
        print(f"Database error: {e}")  # 데이터베이스 연결 중에 발생한 오류 메시지 출력
        return None


def control_motor(timer):
    url = "http://192.168.0.13:80/feed"  # 수정된 부분
    data = {'timer': timer} # ex) {'timer' : 5000} 5초동안 모터 동작. 1000 = 1초
    try:
        response = requests.post(url, json=data, timeout=5)  # 수정된 부분
        response.raise_for_status() # 오류코드 400 이상이면 에러
    except requests.ConnectionError:
        print(
            "Error: Unable to connect to the server. Please check the server address and whether the server is running.")
        return None
    except requests.Timeout:
        print(f"Error: Request to {url} timed out.")
        return None
    except requests.RequestException as e:
        print(f"Error: An error occurred while sending the request. {str(e)}")
        return None

    print(f"Success: Server responded with {response.status_code}.")
    return None

DEFAULT_INTERVAL = 1 # 기본 배급 간격을 1분으로 설정

def main():
    try:
        command = "python detect.py --weights best.pt --img 608 --conf 0.85 --source http://192.168.0.13:81/stream"
        #아두이노에서 static ip 주소로 고정
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        user_id = 1  # 예시로 1을 사용하였으나 실제 환경에 맞게 변경하셔야 합니다.
        last_feeding_time = datetime.now() - timedelta(hours=24)  # 초기화, 최초 실행시 24시간 전으로 설정

        for line in process.stdout:
            if "Detected breed:" in line:
                # "Detected breed:" 문자열 다음에 오는 문자열(품종 이름)을 추출합니다.
                detected_breed = line.split("Detected breed:")[1].strip()
                print(f"Extracted breed: {detected_breed}")

                # 새로운 추가된 부분: detected_breed를 기반으로 can_proceed 함수를 호출하여
                # 특정 시간이 지났는지 확인합니다.
                if can_proceed(detected_breed):  # 특정 시간이 경과하였는지 확인합니다.
                    interval = get_feed_interval(user_id)
                    if interval is None:
                        interval = DEFAULT_INTERVAL  # 기본 1분으로 설정

                    if datetime.now() - last_feeding_time >= timedelta(minutes=interval):
                        if is_time_restricted(user_id):
                            print("Feeding is restricted at this time.")
                        else:
                            default_feed_amount = get_default_feed_amount(detected_breed)
                            if default_feed_amount:
                                control_motor(default_feed_amount)
                                log_detection(detected_breed)  # 모터가 동작한 후에 감지 이력을 데이터베이스에 기록합니다.
                                last_feeding_time = datetime.now()  # 마지막 피딩 시간 업데이트
                            else:
                                print(f"No default feed amount found for breed: {detected_breed}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()