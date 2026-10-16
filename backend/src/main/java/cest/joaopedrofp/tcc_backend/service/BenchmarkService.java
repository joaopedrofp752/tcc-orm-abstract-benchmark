package cest.joaopedrofp.tcc_backend.service;

import cest.joaopedrofp.tcc_backend.dto.PayloadDTO;
import java.util.List;

public interface BenchmarkService {
    List<PayloadDTO> fetchPayloadData(int limit);
}