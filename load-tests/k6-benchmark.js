import http from 'k6/http';
import { check, sleep } from 'k6';

const limit = __ENV.LIMIT || 200;
const stageTime = __ENV.STAGE_TIME || '15s';

export const options = {
    // Stepped load progression in 15s intervals reaching peak 55 VUs (90s total)
    stages: [
        { duration: stageTime, target: 5 },
        { duration: stageTime, target: 13 },
        { duration: stageTime, target: 21 },
        { duration: stageTime, target: 34 },
        { duration: stageTime, target: 55 },
        { duration: stageTime, target: 0 },
    ],
    // Prevent k6 runtime memory bloating during continuous metric dumps
    discardResponseBodies: true,
};

export default function () {
    const url = `http://localhost:8080/api/benchmark/payloads?limit=${limit}`;
    const params = {
        headers: {
            'Accept': 'application/json',
        },
        timeout: '5s',
    };

    const res = http.get(url, params);

    check(res, {
        'status is 200': (r) => r.status === 200,
        'response time < 2000ms': (r) => r.timings.duration < 2000,
    });

    // 100ms pacing between requests to sustain high concurrency pressure
    sleep(0.1);
}
