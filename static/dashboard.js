// 데이터를 HTML 요소의 data- 속성에서 가져옵니다.
var dataContainer = document.getElementById('dataContainer');
var timestamps = JSON.parse(dataContainer.getAttribute('data-timestamps'));
var temperatures = JSON.parse(dataContainer.getAttribute('data-temperatures'));
var humidities = JSON.parse(dataContainer.getAttribute('data-humidities'));
var weights = JSON.parse(dataContainer.getAttribute('data-weights'));

// 꺾은선 그래프
var ctx1 = document.getElementById('tempHumidityChart').getContext('2d');
var tempHumidityChart = new Chart(ctx1, {
    type: 'line',
    data: {
        labels: timestamps,
        datasets: [{
            label: '온도',
            data: temperatures,
            borderColor: 'red',
            fill: false
        }, {
            label: '습도',
            data: humidities,
            borderColor: 'blue',
            fill: false
        }]
    }
});

// 막대 그래프
var ctx2 = document.getElementById('weightBarChart').getContext('2d');
var weightBarChart = new Chart(ctx2, {
    type: 'bar',
    data: {
        labels: timestamps,
        datasets: [{
            label: '무게',
            data: weights,
            backgroundColor: 'green'
        }]
    }
});

// 실시간 무게 업데이트
var socket = io.connect('http://localhost:5000');
socket.on('update_weight', function(data) {
    document.getElementById('weightValue').innerText = data.weight;
});
