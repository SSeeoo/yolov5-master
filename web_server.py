# web_server.py
from flask import Flask, request, jsonify, render_template
import pymysql
from sqlalchemy.ext.asyncio import engine

from Smart_feeder import control_motor, is_time_restricted # Smart_feeder.py 파일에서 control_motor 함수를 가져옴
import os
import logging
from datetime import datetime
import plotly.express as px
import plotly.io as pio
import pandas as pd
import json
from sqlalchemy import create_engine, text

app = Flask(__name__)

# 로그 설정
logging.basicConfig(level=logging.DEBUG)

@app.route('/set_interval', methods=['POST'])
def set_interval():
    try:
        user_id = request.json.get('user_id')
        interval_minutes = request.json.get('interval_minutes')

        # 데이터 유효성 검사
        if user_id is None or interval_minutes is None:
            return jsonify({'status': 'error', 'message': 'Invalid data received'}), 400

        # 데이터베이스에 데이터 저장
        with pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '5611'),
            db=os.getenv('DB_NAME', 'feeder'),
            charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                sql = """INSERT INTO feed_interval (user_id, interval_minutes)
                         VALUES (%s, %s) ON DUPLICATE KEY UPDATE interval_minutes = %s"""
                cursor.execute(sql, (user_id, interval_minutes, interval_minutes))
                conn.commit()

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred'}), 500


@app.route('/set_time_restriction', methods=['POST'])
def set_time_restriction():
    try:
        user_id = request.json.get('user_id')
        start_time = request.json.get('start_time')  # 'HH:MM:SS' 형식의 문자열로 받을 수 있습니다.
        end_time = request.json.get('end_time')  # 'HH:MM:SS' 형식의 문자열로 받을 수 있습니다.

        if not user_id or not start_time or not end_time:
            return jsonify({'status': 'error', 'message': 'user_id, start_time, and end_time are required'}), 400

        # 받은 시간 제한을 데이터베이스에 저장
        with pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '5611'),
            db=os.getenv('DB_NAME', 'feeder'),
            charset='utf8'
        ) as conn:
            with conn.cursor() as cursor:
                sql = "INSERT INTO time_restriction (user_id, start_time, end_time) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE start_time = %s, end_time = %s"
                cursor.execute(sql, (user_id, start_time, end_time, start_time, end_time))
                conn.commit()

        return jsonify(status='success'), 200
    except Exception as e:
        return jsonify(status='error', message=str(e)), 400

# 웹페이지 생성을 위해 새로 추가된 코드
# DB에서 데이터를 가져오는 함수
def fetch_detection_data():
    try:
        # SQLAlchemy 엔진을 만듭니다.
        database_uri = f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '5611')}@{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME', 'feeder')}"
        engine = create_engine(database_uri)

        sql = "SELECT * FROM detection_log"

        # pd.read_sql을 이용하여 SQL 쿼리 결과를 DataFrame으로 읽어옵니다.
        # AttributeError: 'OptionEngine' object has no attribute 'execute' 에러 해결 방법 : text
        df = pd.read_sql(sql=text(sql), con=engine.connect())

        # 'time' 열을 datetime 형태로 변환합니다.
        df['time'] = pd.to_datetime(df['time'])

        return df
    except Exception as e:
        logging.error(f"Error fetching detection data: {e}")
        return pd.DataFrame()


### 웹페이지 구성
def convert_df_to_json_format(df):
    # Convert DataFrame to JSON string
    json_str = df.to_json(orient='split')

    # Convert JSON string to dictionary
    json_data = json.loads(json_str)

    return json_data

@app.route('/')
def index():
    try:
        # 예제로, 실제로는 DB에서 breed 리스트를 가져와야 합니다.
        # breeds = ['dog-beagle', 'cat-Persian', ...]
        breeds = get_all_breeds_from_db()  # 데이터베이스에서 모든 breeds를 가져옵니다.
        graph_html = "<p>Initial Graph HTML</p>"  # 초기 그래프 HTML
        return render_template('detection_graph.html', graph_html=graph_html, breeds=breeds)
    except Exception as e:
        print(f"Error loading index: {e}")
        return render_template('error.html', error=str(e)), 500

def get_all_breeds_from_db():
    # breeds를 저장할 리스트를 생성합니다.
    breeds = []
    try:
        # engine을 사용하여 데이터베이스에 연결합니다.
        with engine.connect() as connection:
            # petbreed 테이블에서 BreedName을 선택하여 가져옵니다.
            result = connection.execute("SELECT BreedName FROM petbreed")
            # 결과로부터 모든 breed 이름을 리스트에 추가합니다.
            breeds = [row[0] for row in result]
    except Exception as e:
        logging.error(f"Error fetching breeds from DB: {e}")
    return breeds



@app.route('/get_graph_data', methods=['POST'])
def get_graph_data():
    try:
        selected_breeds = request.json.get('selected_breeds', [])
        # 선택된 breeds에 따라 그래프 데이터를 가져옵니다.
        graph_html = "<p>Updated Graph HTML for " + ", ".join(selected_breeds) + "</p>"
        return jsonify(status='success', graph_html=graph_html)

    except Exception as e:
        print(f"Error getting graph data: {e}")
        return jsonify(error=str(e)), 500


@app.route('/get_logs_for_breeds', methods=['POST'])
def get_logs_for_breeds():
    try:
        selected_breeds = request.json.get('selected_breeds', [])

        # selected_breeds가 비어있지 않을 때만 로그를 가져옵니다.
        if selected_breeds:
            with engine.connect() as connection:
                # IN 절을 사용하여 선택된 breeds에 해당하는 로그만 가져옵니다.
                sql = text("SELECT breed, time FROM detection_log WHERE breed IN :breeds")
                result = connection.execute(sql, breeds=tuple(selected_breeds)).fetchall()

                # 결과를 JSON으로 변환 가능한 형태로 만듭니다.
                logs = [{"breed": row[0], "time": str(row[1])} for row in result]
                return jsonify(status='success', logs=logs), 200
        else:
            return jsonify(status='success', logs=[]), 200
    except Exception as e:
        logging.error(f"Error fetching logs for breeds: {e}")
        return jsonify(status='error', message=str(e)), 500


@app.route('/get_table_data', methods=['POST'])
def get_table_data():
    try:
        selected_breeds = request.json.get('selected_breeds', [])
        # 선택된 breeds에 따라 테이블 데이터를 가져옵니다.
        table_html = "<p>Updated Table HTML for " + ", ".join(selected_breeds) + "</p>"
        return jsonify(status='success', table_html=table_html)

    except Exception as e:
        print(f"Error getting table data: {e}")
        return jsonify(error=str(e)), 500

@app.route('/detection_graph', methods=['GET'])
def detection_graph():
    try:
        df = fetch_detection_data()

        # 일자와 시간대별로 그룹화
        df['datetime'] = pd.to_datetime(df['time'])
        df.set_index('datetime', inplace=True)

        # 분 단위 그룹화
        summary_df = df.groupby([df.index.floor('T'), 'breed']).size().reset_index(name='counts')
        summary_df.rename(columns={'datetime': 'date'}, inplace=True)

        # 그래프 그리기
        fig = px.line(summary_df, x='date', y='counts', color='breed',
                      labels={'counts': 'Feeding Counts', 'date': 'Date'},
                      title='Feeding Counts by Breed and Date')

        # X축의 날짜와 시간 설정
        fig.update_xaxes(
            tickformat="%Y-%m-%d %H:%M",  # Display both date and time
        )
        # Y축의 간격 설정
        fig.update_yaxes(
            dtick=1  # Y축 간격을 1로 설정
        )

        # Plotly를 사용하여 HTML 문자열로 그래프 변환
        graph_html = pio.to_html(fig, full_html=False)

        return render_template('detection_graph.html', graph_html=graph_html)

    except Exception as e:
        logging.error(f"Error creating detection graph: {e}")
        return render_template('error.html', error_message=str(e))


@app.route('/feed', methods=['POST'])
def feed():
    try:
        # print문 대신 로그를 사용 - 수정된 부분
        logging.info("Feed Request Received")
        timer = int(request.json.get('timer', 0))  # 수정된 부분
        control_motor(timer)
        logging.info("Feed successful")
        return "Feed successful", 200
    except Exception as e:
        logging.error(f"Error: {e}")
        return "Feed failed", 400

# 새로운 함수 정의 - force 파라미터가 True로 전달 되면, can_proceed를 무시하고 모터를 작동
@app.route('/control_motor', methods=['POST'])
def control_motor_endpoint():
    force = request.json.get('force', False)

    if is_time_restricted(1) and not force: # user_id: 1로 임시 설정
        return {'status': 'error', 'message': 'Restricted time'}, 403

    # 모터 작동 로직
    timer = request.json.get('timer', 0)
    control_motor(timer)

    return {'status': 'success'}, 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
