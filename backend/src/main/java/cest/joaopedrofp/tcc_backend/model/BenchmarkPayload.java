package cest.joaopedrofp.tcc_backend.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "benchmark_payload")
public class BenchmarkPayload {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "payload_data", nullable = false)
    private String payloadData;

    public BenchmarkPayload() {
    }

    public BenchmarkPayload(Long id, String payloadData) {
        this.id = id;
        this.payloadData = payloadData;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getPayloadData() {
        return payloadData;
    }

    public void setPayloadData(String payloadData) {
        this.payloadData = payloadData;
    }
}