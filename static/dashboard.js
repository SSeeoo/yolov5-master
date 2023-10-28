// 데이터를 HTML 요소의 data- 속성에서 가져옵니다.
var dataContainer = document.getElementById('dataContainer');

function parseJSONData(attribute) {
    var data = dataContainer.getAttribute(attribute);
    if (data && data !== "null") {
        try {
            return JSON.parse(data);
        } catch (e) {
            console.error("Error parsing JSON data from attribute:", attribute, data);
            return [];
        }
    } else {
        return [];
    }
}

var timestamps = parseJSONData('data-timestamps');
var temperatures = parseJSONData('data-temperatures');
var humidities = parseJSONData('data-humidities');
var weights = parseJSONData('data-weights');

// 꺾은선 그래프
var ctx1 = document.getElementById('tempHumidityChart').getContext('2d');
var tempHumidityChart = new Chart(ctx1, {
    type: 'line',
    responsive: false,  // 그래프의 반응성을 비활성화
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
    responsive: false,  // 그래프의 반응성을 비활성화
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
var socket = io.connect('http://127.0.0.1:5000');
socket.on('update_weight', function(data) {
    document.getElementById('weightValue').innerText = data.weight;
});
