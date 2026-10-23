import http from 'k6/http';
import { check } from 'k6';

const limit = __ENV.LIMIT || 200;
const scenarioName = __ENV.SCENARIO || 'nominal';
const isWarmup = __ENV.WARMUP === 'true';

const SCENARIOS = {
    nominal: {
        rate: 300,
        preAllocatedVUs: 30,
        maxVUs: 90,
        duration: '90s',
    },
    saturation: {
        rate: 1200,
        preAllocatedVUs: 120,
        maxVUs: 360,
        duration: '90s',
    },
    warmup: {
        rate: 100,
        preAllocatedVUs: 10,
        maxVUs: 30,
        duration: '60s',
    },
};

const active = isWarmup ? SCENARIOS.warmup : (SCENARIOS[scenarioName] || SCENARIOS.nominal);

export const options = {
    scenarios: {
        benchmark_execution: {
            executor: 'constant-arrival-rate',
            rate: active.rate,
            timeUnit: '1s',
            duration: active.duration,
            preAllocatedVUs: active.preAllocatedVUs,
            maxVUs: active.maxVUs,
        },
    },
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
}
