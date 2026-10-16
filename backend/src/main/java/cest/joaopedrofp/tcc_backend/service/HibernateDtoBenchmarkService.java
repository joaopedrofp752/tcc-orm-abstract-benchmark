package cest.joaopedrofp.tcc_backend.service;

import cest.joaopedrofp.tcc_backend.dto.PayloadDTO;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class HibernateDtoBenchmarkService implements BenchmarkService {

    @PersistenceContext
    private final EntityManager entityManager;

    public HibernateDtoBenchmarkService(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    @Override
    @Transactional(readOnly = true)
    public List<PayloadDTO> fetchPayloadData(int limit) {
        String jpql = "SELECT new cest.joaopedrofp.tcc_backend.dto.PayloadDTO(p.id, p.payloadData) " +
                "FROM BenchmarkPayload p ORDER BY p.id ASC";

        return entityManager.createQuery(jpql, PayloadDTO.class)
                .setMaxResults(limit)
                .getResultList();
    }
}