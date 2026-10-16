package cest.joaopedrofp.tcc_backend.controller;

import cest.joaopedrofp.tcc_backend.dto.PayloadDTO;
import cest.joaopedrofp.tcc_backend.service.BenchmarkService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/benchmark")
public class BenchmarkController {

    private final BenchmarkService benchmarkService;

    // required = false allows the sterile 'main' branch to boot without an active implementation
    public BenchmarkController(@Autowired(required = false) BenchmarkService benchmarkService) {
        this.benchmarkService = benchmarkService;
    }

    // Health check endpoint for battery orchestration pre-flight
    @GetMapping("/health")
    public ResponseEntity<Void> healthCheck() {
        return ResponseEntity.ok().build();
    }

    @GetMapping("/payloads")
    public List<PayloadDTO> getPayloads(@RequestParam(defaultValue = "200") int limit) {
        if (benchmarkService == null) {
            return Collections.emptyList();
        }
        return benchmarkService.fetchPayloadData(limit);
    }
}