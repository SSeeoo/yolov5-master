// 시작할 때 사용 가능한 모든 breed를 가져옵니다.
fetchBreeds();

function fetchBreeds() {
    // 이 부분은 /get_all_breeds 엔드포인트를 호출하여 사용 가능한 모든 breed를 가져옵니다.
    // 가져온 breed는 위의 <select> 태그에 추가됩니다.
}

function fetchLogs() {
    // 사용자가 선택한 날짜와 breed를 가져옵니다.
    const date = document.getElementById('date').value;
    const breed = document.getElementById('breed').value;

    // /get_feed_history 엔드포인트를 호출하여 해당 조건의 로그를 가져옵니다.
    // 가져온 로그는 위의 <tbody> 태그에 추가됩니다.
}
