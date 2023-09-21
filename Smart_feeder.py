import subprocess
import pymysql
import json
import requests

def get_default_feed_amount(breed):
    try:
        with pymysql.connect(host='localhost', user='root', password='5611', db='feeder', charset='utf8') as conn:
            with conn.cursor() as cursor:
                sql = "SELECT DefaultFeedAmount FROM petbreed WHERE BreedName = %s"
                cursor.execute(sql, (breed,))
                result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Database error: {e}")
        return None


def control_motor(amount):
    try:
        # ESP32 카메라에 feed 요청을 보냄
        requests.post("http://192.168.0.8:80/feed", data={'amount': amount})
    except Exception as e:
        print(f"Request error: {e}")
        return None


def parse_output(output): # json type으로 설정
    try:
        parsed_data = json.loads(output)
        breed = parsed_data.get("breed", None)
        confidence = parsed_data.get("confidence", 0)

        if breed and confidence > 0.85:  # conf 0.85
            return breed
        else:
            return None
    except json.JSONDecodeError:
        print("Error decoding JSON output")
        return None


def main():
    try:
        command = "python detect.py --weights best.pt --img 608 --conf 0.85 --source http://192.168.0.8:81/stream"
        # 192.168.0.13으로 웹서버 static ip로 고정
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        output, _ = process.communicate()

        detected_breed = parse_output(output.decode('utf-8'))

        default_feed_amount = get_default_feed_amount(detected_breed)

        if default_feed_amount:
            control_motor(default_feed_amount)
        else:
            print(f"No default feed amount found for breed: {detected_breed}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
