package cest.joaopedrofp.tcc_backend.service;

import cest.joaopedrofp.tcc_backend.dto.PayloadDTO;
import cest.joaopedrofp.tcc_backend.model.BenchmarkPayload;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class HibernateBenchmarkService implements BenchmarkService {

    @PersistenceContext
    private final EntityManager entityManager;

    public HibernateBenchmarkService(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    @Override
    @Transactional(readOnly = true)
    public List<PayloadDTO> fetchPayloadData(int limit) {
        String jpql = "SELECT p FROM BenchmarkPayload p ORDER BY p.id ASC";

        List<BenchmarkPayload> entities = entityManager.createQuery(jpql, BenchmarkPayload.class)
                .setMaxResults(limit)
                .getResultList();

        return entities.stream()
                .map(entity -> new PayloadDTO(entity.getId(), entity.getPayloadData()))
                .toList();
    }
}