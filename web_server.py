# web_server.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from sqlalchemy import create_engine, text
import hashlib
import os
import logging
import plotly.express as px
import plotly.io as pio
import pandas as pd
import json
import traceback
import sys
from Smart_feeder import control_motor, is_time_restricted
from werkzeug.security import generate_password_hash, check_password_hash

# from decouple import config
# from models import db, User
# import pymysql
# from sqlalchemy.ext.asyncio import AsyncSession
# from datetime import datetime

# SQLAlchemy 엔진 생성 로직을 함수로 분리
def create_db_engine():
    database_uri = (f"mysql+pymysql://"
                    f"{os.getenv('DB_USER', 'root')}:"
                    f"{os.getenv('DB_PASSWORD', '5611')}@"
                    f"{os.getenv('DB_HOST', 'localhost')}/"
                    f"{os.getenv('DB_NAME', 'feeder')}")
    return create_engine(database_uri)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'secret')  # 환경변수에서 읽어옴
engine = create_db_engine()  # 엔진 생성

# 로그 설정
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)



@app.route('/set_interval', methods=['POST'])
def set_interval():
    data = request.json
    required_keys = ['user_id', 'interval_minutes']

    # 필요한 키가 누락된 경우 에러 응답
    if not all(key in data for key in required_keys):
        return jsonify({'status': 'error', 'message': 'Invalid data received'}), 400

    with engine.connect() as conn:
        sql = """INSERT INTO feed_interval (user_id, interval_minutes)
                 VALUES (:user_id, :interval_minutes)
                 ON DUPLICATE KEY UPDATE interval_minutes = :interval_minutes"""
        conn.execute(text(sql), **data)  # 바인딩 된 인자를 딕셔너리로 전달

    return jsonify({'status': 'success'}), 200


@app.route('/set_time_restriction', methods=['POST'])
def set_time_restriction():
    data = request.json
    required_keys = ['user_id', 'start_time', 'end_time']

    if not all(key in data for key in required_keys):
        return jsonify({'status': 'error', 'message': 'user_id, start_time, and end_time are required'}), 400

    with engine.connect() as conn:
        sql = """INSERT INTO time_restriction (user_id, start_time, end_time) 
                 VALUES (:user_id, :start_time, :end_time) 
                 ON DUPLICATE KEY UPDATE start_time = :start_time, end_time = :end_time"""
        conn.execute(text(sql), **data)

    return jsonify(status='success'), 200

# 웹페이지 생성을 위해 새로 추가된 코드
# DB에서 데이터를 가져오는 함수
def fetch_detection_data():
    try:
        # SQL 쿼리를 작성합니다.
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


# 웹페이지 구성
def convert_df_to_json_format(df):
    # Convert DataFrame to JSON string
    json_str = df.to_json(orient='split')

    # Convert JSON string to dictionary
    json_data = json.loads(json_str)

    return json_data

@app.route('/')
def index():
    try:
        breeds = get_all_breeds_from_db() # DB에서 모든 breed를 가져옵니다.
        return render_template('login.html', breeds=breeds)
    except Exception as e:
        logging.error(f"Error loading index: {e}")
        return render_template('error.html', error=str(e)), 500

def get_all_breeds_from_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT BreedName FROM petbreed"))
            breeds = [row[0] for row in result]
        return breeds
    except Exception as e:
        logging.error(f"Error fetching breeds from DB: {e}")
        return []

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()  # 비밀번호를 해시로 변환


@app.route('/sign_in', methods=['POST'])
def sign_in():
    try:
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify(status='error', message='Username and Password are required'), 400

        with engine.connect() as conn:
            sql = "SELECT * FROM users WHERE username = :username"
            result = conn.execute(text(sql), {"username": username}).fetchone()

        # 사용자가 존재하고 해시 비밀번호가 일치하는지 확인합니다.
        if result and check_password_hash(result[2], password): # result[2] : password
            session['username'] = username  # 로그인 성공 시 세션에 username 저장
            return redirect(url_for('dashboard'))  # 로그인 성공 시 /dashboard로 리다이렉트
        else:
            return jsonify(status='error', message='Invalid credentials'), 401
    except Exception as e:
        logging.error(f"Error: {e}")
        logging.error(traceback.format_exc())
        return jsonify(status='error', message=str(e)), 400

@app.route('/sign_up', methods=['POST'])
def sign_up():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if not username or not password or not email:
            return jsonify(status='error', message='Username, Password, and Email are required'), 400

        hashed_password = generate_password_hash(password)

        with engine.connect() as conn:
            sql = "INSERT INTO users (username, password, email) VALUES (:username, :password, :email)"
            conn.execute(text(sql), {"username": username, "password": hashed_password, "email": email})
            conn.commit()

        return jsonify(status='success', message='Sign up successful')
    except Exception as e:
        logging.error(f"Error: {e}")
        logging.error(traceback.format_exc())
        return jsonify(status='error', message=str(e)), 400


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:  # 세션에 username이 존재하지 않으면 /login으로 리다이렉트
        return redirect(url_for('login'))
    return render_template('dashboard.html',username=session['username'])  # username이 존재하면 dashboard.html 렌더링


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

        if selected_breeds:
            database_uri = f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '5611')}@{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME', 'feeder')}"
            engine = create_engine(database_uri, future=True)

            with engine.connect() as conn:
                sql = text("SELECT breed, time FROM detection_log WHERE breed IN :breeds")
                result = conn.execute(sql, {"breeds": selected_breeds}).fetchall()

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
    timer = request.json.get('timer', 0)

    # 시간 제한이 있는 경우와 force가 True인 경우를 확인합니다.
    if is_time_restricted(1) and not force: # user_id: 1로 임시 설정
        return {'status': 'error', 'message': 'Restricted time'}, 403

    # 모터 작동 로직
    control_motor(timer)

    return {'status': 'success'}, 200

@app.route('/get_feed_history', methods=['GET'])
def get_feed_history():
    try:
        with engine.connect() as conn:
            sql = text("SELECT breed, time FROM detection_log")
            result = conn.execute(sql).fetchall()

            # 가져온 데이터를 JSON 형태로 변환합니다.
            feed_history = [{"breed": row[0], "time": str(row[1])} for row in result]

        return jsonify(status='success', feed_history=feed_history), 200

    except Exception as e:
        logging.error(f"Error fetching feed history: {e}")
        return jsonify(status='error', message=str(e)), 500


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True, port=5000)
