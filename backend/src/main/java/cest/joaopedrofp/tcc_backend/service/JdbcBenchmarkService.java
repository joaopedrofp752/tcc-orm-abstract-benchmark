package cest.joaopedrofp.tcc_backend.service;

import cest.joaopedrofp.tcc_backend.dto.PayloadDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class JdbcBenchmarkService implements BenchmarkService {

    private final JdbcTemplate jdbcTemplate;

    public JdbcBenchmarkService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public List<PayloadDTO> fetchPayloadData(int limit) {
        String sql = "SELECT id, payload_data FROM benchmark_payload ORDER BY id LIMIT ?";

        return jdbcTemplate.query(
                sql,
                (rs, rowNum) -> new PayloadDTO(
                        rs.getLong("id"),
                        rs.getString("payload_data")
                ),
                limit
        );
    }
}