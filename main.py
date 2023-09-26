import subprocess

# 두 스크립트를 병렬로 실행하기 위해 Popen 객체를 생성합니다.
process1 = subprocess.Popen(["python", "web_server.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
process2 = subprocess.Popen(["python", "Smart_feeder.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 두 프로세스가 종료될 때까지 기다립니다.
process1.wait()
process2.wait()
