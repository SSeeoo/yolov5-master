# web_server.py
from flask import Flask, request
from Smart_feeder import control_motor  # Smart_feeder.py 파일에서 control_motor 함수를 가져옴

app = Flask(__name__)

@app.route('/feed', methods=['POST'])
def feed():
    try:
        timer = int(request.form.get('timer', 0))  # 폼에서 timer 값을 가져옴
        control_motor(timer)  # 모터를 동작시킴
        return "Feed successful", 200
    except Exception as e:
        print(f"Error: {e}")
        return "Feed failed", 400


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
