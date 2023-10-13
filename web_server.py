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
from sqlalchemy import Column, Integer, Float, DateTime, cast
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from flask_socketio import SocketIO

# from decouple import config
# from models import db
# import pymysql
# from sqlalchemy.ext.asyncio import AsyncSession

# Flask 앱 및 SQLAlchemy 엔진 설정
app = Flask(__name__)

# SQLAlchemy 엔진 생성 로직을 함수로 분리
def create_db_engine():
    database_uri = (f"mysql+pymysql://"
                    f"{os.getenv('DB_USER', 'root')}:"
                    f"{os.getenv('DB_PASSWORD', '5611')}@"
                    f"{os.getenv('DB_HOST', 'localhost')}/"
                    f"{os.getenv('DB_NAME', 'feeder')}")
    return create_engine(database_uri)

app.secret_key = os.getenv('SECRET_KEY', 'secret')  # 환경변수에서 읽어옴
engine = create_db_engine()  # 엔진 생성

Base = declarative_base()
Base.metadata.create_all(engine) # 데이터베이스에 테이블 생성

# 데이터 모델 정의
class SensorData(Base):
    __tablename__ = 'sensor_data'

    id = Column(Integer, primary_key=True)
    temperature = Column(Float)
    humidity = Column(Float)
    weight = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Socket.io 설정
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('get_weight')
def handle_weight():
    # 여기서 데이터베이스에서 최신 무게 데이터를 가져옵니다.
    latest_weight = SensorData.query.order_by(SensorData.timestamp).first().weight
    socketio.emit('update_weight', {'weight': latest_weight})

# 로그 설정
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Flask 라우트 정의
@app.route('/save_sensor_data', methods=['POST'])
def save_sensor_data():
    try:
        # 요청으로부터 데이터를 받습니다.
        temperature = float(request.form.get('temperature'))
        humidity = float(request.form.get('humidity'))
        weight = float(request.form.get('weight'))

        data = SensorData(temperature=temperature, humidity=humidity, weight=weight)

        # 세션 생성
        Session = sessionmaker(bind=engine)
        session = Session()

        session.add(data)
        session.commit()
        session.close()

        return "Data saved successfully", 200
    except Exception as e:
        return str(e), 400

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

@app.route('/', methods=['POST'])
def handle_post():
    try:
        temperature = request.form.get('temperature')
        humidity = request.form.get('humidity')
        weight = request.form.get('weight')

        data = SensorData(temperature=temperature, humidity=humidity, weight=weight)

        # 세션 생성
        Session = sessionmaker(bind=engine)
        session = Session()

        session.add(data)
        session.commit()
        session.close()

        return "Data received", 200
    except Exception as e:
        return str(e), 400

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

@app.route('/check_session')
def check_session():
    return f"Username in session: {session.get('username', 'Not set')}"

@app.route('/dashboard')
def dashboard():
    # 세션에서 사용자 이름 가져오기
    user = session.get('username', '')

    try:
        # 최근 24시간 동안의 데이터를 가져옵니다.
        past_24_hours = datetime.now() - timedelta(days=1)

        # past_24_hours의 값을 콘솔에 출력합니다. ( 테스트용 )
        print("Value of past_24_hours:", past_24_hours)
        print("Type of past_24_hours:", type(past_24_hours))

        # SQLAlchemy 세션을 사용하여 쿼리를 수행
        Session = sessionmaker(bind=engine)
        db_session = Session() # 이름 중복으로 db_session으로 변경
        sensor_data = db_session.query(SensorData).filter(SensorData.timestamp > cast(past_24_hours, DateTime)).all()
        db_session.close()

        # 데이터를 그래프에 사용할 수 있는 형식으로 변환합니다.
        timestamps = [data.timestamp.strftime('%Y-%m-%d %H:%M:%S') for data in sensor_data]
        temperatures = [data.temperature for data in sensor_data]
        humidities = [data.humidity for data in sensor_data]
        weights = [data.weight for data in sensor_data]

        return render_template('dashboard.html', user=user, timestamps=timestamps, temperatures=temperatures, humidities=humidities, weights=weights)
    except Exception as e:
        logging.error(f"Error in /dashboard: {e}")  # 오류 메시지를 로깅합니다.
        logging.error(traceback.format_exc())  # 트레이스백을 로깅합니다.
        return str(e), 400


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

    if is_time_restricted(1) and not force:  # user_id: 1로 임시 설정
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


# Socket.io 이벤트 핸들러
@socketio.on('connect')
def connect():
    print('Connected')

@socketio.on('disconnect')
def disconnect(sid):
    print('Disconnected', sid)

@socketio.on('update_weight')
def update_weight(sid, data):
    socketio.emit('update_weight', {'weight': data['weight']}, room=sid)

# Flask 앱 실행
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
