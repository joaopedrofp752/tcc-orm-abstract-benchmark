import http from 'k6/http';
import { check, sleep } from 'k6';

const limit = __ENV.LIMIT || 200;
const stageTime = __ENV.STAGE_TIME || '45s';
const targetEndpoint = __ENV.TARGET_ENDPOINT || 'payloads';

export const options = {
    stages: [
        { duration: stageTime, target: 5 },
        { duration: stageTime, target: 8 },
        { duration: stageTime, target: 13 },
        { duration: stageTime, target: 21 },
        { duration: stageTime, target: 34 },
        { duration: stageTime, target: 55 },
        { duration: '30s', target: 0 },
    ],
    // Prevents k6 from dropping metric points when disk I/O spikes during CSV dumps
    discardResponseBodies: false,
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

    sleep(1);
}
